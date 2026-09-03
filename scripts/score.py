#!/usr/bin/env python3
"""
Compute the independent AI-visibility scoring model from raw evidence JSON.

Reads every evidence/<date>/core_*.json file, computes the 10 metrics defined
in the audit methodology, and writes metrics/<date>.json plus an updated
metrics/history.json (append-only, used for 7/30/90-day trends).

Never estimates a missing value. If there isn't enough history for a trend,
the trend fields are written as null with a "reason", not guessed.
"""
import json
import glob
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVIDENCE_DIR = os.path.join(REPO, "evidence")
METRICS_DIR = os.path.join(REPO, "metrics")

# The original watch-list from the brief, used to seed competitor tracking.
# Any other org appearing in evidence is an "emerging" competitor, not on
# this seed list.
SEED_COMPETITORS = {
    "Johnson Controls", "Honeywell", "Schneider Electric", "Siemens",
    "SensorFlow", "Verdant", "SMS Energy", "Mitie", "Equans",
    "Hospitality Energy Saving & Sustainability", "Concept Energy Solutions",
    "Mission Net Zero",
}

HIGH_INTENT_STAGES = {"decision", "purchase-intent"}

# Very rough source-quality tiers for the source-quality score. Anything not
# matched falls into "unclassified" and is excluded from the weighted score
# (never silently scored as low- or high-quality by guesswork).
GOV_DOMAINS = (".gov.uk", "gov.uk")
TRADE_PUB_DOMAINS = (
    "hospitalitynet.org", "hospitality-net.org", "boutiquehotelnews.com",
    "hotelmanagement.net", "hotelownership.co.uk", "hotelowner.co.uk",
    "hoteltechnologynews.com", "hospitalityinvestor.com", "edie.net",
    "greenhotelier.org", "ukhospitality.org.uk",
)
LOW_VALUE_DOMAINS = ("directory", "listing")


def load_all_records():
    records = []
    for path in sorted(glob.glob(os.path.join(EVIDENCE_DIR, "*", "core_15.json"))):
        with open(path) as f:
            doc = json.load(f)
        for r in doc["records"]:
            r["_run_date"] = doc["run_date"]
            records.append(r)
    return records


def classify_source_quality(url):
    if not url:
        return "unclassified"
    u = url.lower()
    if any(d in u for d in GOV_DOMAINS):
        return "government"
    if any(d in u for d in TRADE_PUB_DOMAINS):
        return "trade_publication"
    if any(d in u for d in LOW_VALUE_DOMAINS):
        return "low_value"
    return "general_web"


def compute_metrics(records, run_date):
    n = len(records)
    if n == 0:
        raise SystemExit("No records for this run — refusing to compute metrics from nothing.")

    enz_hits = [r for r in records if r["enz_mentioned"]]
    top3_hits = [r for r in enz_hits if r.get("enz_recommendation_position") and r["enz_recommendation_position"] <= 3]

    # citations: every url in enz_url_cited + every competitor url
    all_citation_urls = []
    for r in records:
        if r.get("enz_url_cited"):
            all_citation_urls.append(r["enz_url_cited"])
        for c in r.get("competitors_mentioned", []):
            if c.get("url"):
                all_citation_urls.append(c["url"])

    owned_citations = [u for u in all_citation_urls if "evolutionnetzero.com" in u]

    # mentions for share of voice
    mention_counter = Counter()
    for r in records:
        if r["enz_mentioned"]:
            mention_counter["Evolution NetZero"] += 1
        for c in r.get("competitors_mentioned", []):
            mention_counter[c["name"]] += 1

    monitored_total = mention_counter["Evolution NetZero"] + sum(
        v for k, v in mention_counter.items() if k != "Evolution NetZero"
    )

    high_intent_records = [r for r in records if r["funnel_stage"] in HIGH_INTENT_STAGES]
    high_intent_hits = [r for r in high_intent_records if r["enz_mentioned"]]

    # content gap: high-value (decision/consideration) prompts where ENZ absent
    # but at least one competitor present
    gap_records = [
        r for r in records
        if not r["enz_mentioned"] and r.get("competitors_mentioned")
        and r["funnel_stage"] in ("decision", "purchase-intent", "consideration")
    ]

    # source quality across all citation urls
    quality_counts = Counter(classify_source_quality(u) for u in all_citation_urls)

    # confidence: based on collection consistency — all core-15 collected same
    # method/engine in one sitting = high; would drop if sources were mixed
    # or partially unavailable
    confidence_inputs = {
        "sample_size": n,
        "target_sample_size": 15,
        "engines_used": sorted(set(r["source_engine"] for r in records)),
        "records_with_all_required_fields": sum(
            1 for r in records if r.get("query") and r.get("date_time_utc") and r.get("source_engine")
        ),
    }
    completeness = confidence_inputs["records_with_all_required_fields"] / n
    sample_ratio = min(1.0, n / confidence_inputs["target_sample_size"])
    # A single search engine/backend cannot represent "AI visibility" broadly —
    # cap the score honestly rather than claim full confidence from one source.
    engine_diversity_cap = 0.85 if len(confidence_inputs["engines_used"]) <= 1 else 1.0
    confidence_score = round((completeness * 0.5 + sample_ratio * 0.5) * engine_diversity_cap * 100, 1)
    confidence_inputs["engine_diversity_cap_applied"] = engine_diversity_cap < 1.0

    metrics = {
        "run_date": run_date,
        "computed_utc": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sample": {"prompts_run": n, "prompts_scheduled": 15, "coverage_pct": round(n / 15 * 100, 1)},

        "independent_visibility_pct": round(len(enz_hits) / n * 100, 1),
        "independent_visibility_evidence": [r["id"] for r in enz_hits],

        "top3_recommendation_rate_pct": round(len(top3_hits) / n * 100, 1),
        "top3_evidence": [r["id"] for r in top3_hits],

        "owned_citation_rate_pct": (
            round(len(owned_citations) / len(all_citation_urls) * 100, 1)
            if all_citation_urls else None
        ),
        "owned_citations": owned_citations,
        "total_citations_captured": len(all_citation_urls),

        "third_party_validation_rate_pct": None,  # requires named third-party review sources; not yet collected — see methodology
        "third_party_validation_note": "Not computed this run: no third-party review/discussion sources were collected yet (see methodology limitations). Do not treat as zero.",

        "competitor_share_of_voice_pct": (
            round(mention_counter["Evolution NetZero"] / monitored_total * 100, 1)
            if monitored_total else None
        ),
        "mention_counts": dict(mention_counter.most_common()),

        "high_intent_visibility_pct": (
            round(len(high_intent_hits) / len(high_intent_records) * 100, 1)
            if high_intent_records else None
        ),
        "high_intent_sample_size": len(high_intent_records),

        "prompt_coverage_pct": round(n / 15 * 100, 1),

        "content_gap_count": len(gap_records),
        "content_gap_prompts": [
            {"id": r["id"], "query": r["query"], "funnel_stage": r["funnel_stage"],
             "competitors_present": [c["name"] for c in r["competitors_mentioned"]]}
            for r in gap_records
        ],

        "source_quality_breakdown": dict(quality_counts),
        "source_quality_note": "Counts by tier across all captured citation URLs (government / trade_publication / general_web / low_value / unclassified). No single 0-100 score is asserted — see methodology for why a single number here would overstate precision.",

        "confidence_score_pct": confidence_score,
        "confidence_inputs": confidence_inputs,

        "new_competitors_this_run": sorted(
            set(mention_counter) - SEED_COMPETITORS - {"Evolution NetZero"}
        ),
    }
    return metrics


def update_history(run_date, metrics):
    hist_path = os.path.join(METRICS_DIR, "history.json")
    if os.path.exists(hist_path):
        with open(hist_path) as f:
            history = json.load(f)
    else:
        history = {"runs": []}

    # de-dupe: replace an existing entry for the same date rather than append twice
    history["runs"] = [r for r in history["runs"] if r["run_date"] != run_date]
    history["runs"].append({
        "run_date": run_date,
        "independent_visibility_pct": metrics["independent_visibility_pct"],
        "top3_recommendation_rate_pct": metrics["top3_recommendation_rate_pct"],
        "owned_citation_rate_pct": metrics["owned_citation_rate_pct"],
        "competitor_share_of_voice_pct": metrics["competitor_share_of_voice_pct"],
        "high_intent_visibility_pct": metrics["high_intent_visibility_pct"],
        "prompt_coverage_pct": metrics["prompt_coverage_pct"],
        "confidence_score_pct": metrics["confidence_score_pct"],
    })
    history["runs"].sort(key=lambda r: r["run_date"])

    with open(hist_path, "w") as f:
        json.dump(history, f, indent=2)
    return history


def compute_trends(history, run_date):
    """7/30/90-day trend = change vs the closest prior run at least that many
    days back. Returns null (not zero, not estimated) when there isn't a
    prior run old enough to compare against."""
    runs = {r["run_date"]: r for r in history["runs"]}
    today = datetime.strptime(run_date, "%Y-%m-%d")
    current = runs[run_date]

    trends = {}
    for label, days in (("7_day", 7), ("30_day", 30), ("90_day", 90)):
        cutoff = today - timedelta(days=days)
        candidates = [r for d, r in runs.items() if datetime.strptime(d, "%Y-%m-%d") <= cutoff]
        if not candidates:
            trends[label] = {
                "available": False,
                "reason": f"No run exists {days}+ days before {run_date} yet. "
                          f"History starts {min(runs) if runs else run_date}.",
            }
            continue
        baseline = max(candidates, key=lambda r: r["run_date"])
        delta = round(current["independent_visibility_pct"] - baseline["independent_visibility_pct"], 1)
        trends[label] = {
            "available": True,
            "baseline_date": baseline["run_date"],
            "independent_visibility_change_pct_points": delta,
        }
    return trends


def main():
    os.makedirs(METRICS_DIR, exist_ok=True)
    all_records = load_all_records()
    by_date = defaultdict(list)
    for r in all_records:
        by_date[r["_run_date"]].append(r)

    for run_date, records in sorted(by_date.items()):
        metrics = compute_metrics(records, run_date)
        history = update_history(run_date, metrics)
        metrics["trends"] = compute_trends(history, run_date)

        out_path = os.path.join(METRICS_DIR, f"{run_date}.json")
        with open(out_path, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"Wrote {out_path}")
        print(f"  independent_visibility: {metrics['independent_visibility_pct']}%")
        print(f"  high_intent_visibility: {metrics['high_intent_visibility_pct']}%")
        print(f"  coverage: {metrics['prompt_coverage_pct']}%  confidence: {metrics['confidence_score_pct']}%")


if __name__ == "__main__":
    main()
