#!/usr/bin/env python3
"""
Generate the plain-English daily briefing from today's metrics vs the
previous run. Sensible thresholds, no manufactured drama: if nothing moved
more than the threshold, the briefing says so plainly.
"""
import json
import os
import sys
from datetime import datetime

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
METRICS_DIR = os.path.join(REPO, "metrics")

# Change thresholds — below these, a movement is noise, not signal.
THRESHOLDS = {
    "independent_visibility_pct": 3.0,   # percentage points
    "high_intent_visibility_pct": 3.0,
    "owned_citation_rate_pct": 2.0,
    "competitor_share_of_voice_pct": 2.0,
}


def load_history():
    with open(os.path.join(METRICS_DIR, "history.json")) as f:
        return json.load(f)["runs"]


def briefing_for(run_date):
    runs = load_history()
    runs_by_date = {r["run_date"]: r for r in runs}
    if run_date not in runs_by_date:
        raise SystemExit(f"No metrics for {run_date} — run scripts/score.py first.")

    current = runs_by_date[run_date]
    prior_dates = sorted(d for d in runs_by_date if d < run_date)
    prior = runs_by_date[prior_dates[-1]] if prior_dates else None

    with open(os.path.join(METRICS_DIR, f"{run_date}.json")) as f:
        full = json.load(f)

    lines = [f"# Daily AI Visibility Briefing — {run_date}", ""]

    if prior is None:
        lines.append("**This is the first recorded run.** There is no prior day to compare against, "
                      "so today establishes the baseline. Nothing below is a change — it's day one.")
        lines.append("")
        lines.append(f"- Independent visibility: **{current['independent_visibility_pct']}%** "
                      f"({len(full['independent_visibility_evidence'])} of {full['sample']['prompts_scheduled']} core prompts)")
        lines.append(f"- High-intent visibility: **{current['high_intent_visibility_pct']}%**")
        lines.append(f"- Owned citation rate: **{current['owned_citation_rate_pct']}%**")
        lines.append(f"- Competitor share of voice: **{current['competitor_share_of_voice_pct']}%**")
        lines.append(f"- Prompt coverage: **{current['prompt_coverage_pct']}%**, confidence **{current['confidence_score_pct']}%**")
        lines.append("")
    else:
        lines.append(f"Compared with the previous run ({prior['run_date']}):")
        lines.append("")
        moved = False
        for key, label in [
            ("independent_visibility_pct", "Independent visibility"),
            ("high_intent_visibility_pct", "High-intent visibility"),
            ("owned_citation_rate_pct", "Owned citation rate"),
            ("competitor_share_of_voice_pct", "Competitor share of voice"),
        ]:
            cur_v, prior_v = current.get(key), prior.get(key)
            if cur_v is None or prior_v is None:
                continue
            delta = round(cur_v - prior_v, 1)
            if abs(delta) >= THRESHOLDS[key]:
                moved = True
                direction = "improved" if delta > 0 else "declined"
                lines.append(f"- **{label} {direction}**: {prior_v}% → {cur_v}% ({delta:+.1f}pp)")
        if not moved:
            lines.append(f"- No metric moved more than its change threshold "
                          f"(thresholds: {', '.join(f'{v}pp' for v in THRESHOLDS.values())}). "
                          f"**Nothing material changed today.**")
        lines.append("")

    new_competitors = full.get("new_competitors_this_run", [])
    if new_competitors:
        lines.append(f"**New organisations observed this run ({len(new_competitors)}):** " + ", ".join(new_competitors[:10]) +
                      (f" and {len(new_competitors) - 10} more" if len(new_competitors) > 10 else ""))
        lines.append("")

    gaps = full.get("content_gap_prompts", [])
    if gaps:
        lines.append(f"**Zero-visibility gaps ({len(gaps)} of {full['sample']['prompts_run']} prompts):** "
                      "questions where a competitor was named and ENZ was not. Full list in the content-gap section.")
        lines.append("")

    unavailable = []
    news_path = os.path.join(REPO, "evidence", run_date, "news_rss.json")
    if os.path.exists(news_path):
        with open(news_path) as f:
            news = json.load(f)
        unavailable = news.get("unavailable_sources", [])
    if unavailable:
        lines.append(f"**Sources unavailable this run:** " + "; ".join(u["source"] for u in unavailable) +
                      ". Marked unavailable, not estimated.")
        lines.append("")

    # Single best action — priority order: Dorset-located decision-stage gaps first
    # (explicit location priority per methodology), then any other decision gap.
    decision_gaps = [g for g in gaps if g["funnel_stage"] in ("decision", "purchase-intent")]
    dorset_gaps = [g for g in decision_gaps if "dorset" in g["query"].lower()]
    decision_gaps = dorset_gaps + [g for g in decision_gaps if g not in dorset_gaps]
    if decision_gaps:
        top = decision_gaps[0]
        action = (f"Close the visibility gap on \"{top['query']}\" — a decision-stage question where "
                  f"{', '.join(top['competitors_present'])} appeared and Evolution NetZero did not. "
                  f"Publish or strengthen a page that directly answers this question with evidence.")
    elif full["independent_visibility_pct"] < 20:
        action = ("Independent visibility is still low overall. Prioritise publishing evidence-rich content "
                   "(quantified case studies, comparison guidance) against the highest-intent gap prompts.")
    else:
        action = "No urgent gap stands out today — hold current publishing plan and re-check tomorrow."

    lines.append(f"## Today's single best action")
    lines.append(action)
    lines.append("")
    lines.append(f"*Generated {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} from {full['sample']['prompts_run']} of "
                 f"{full['sample']['prompts_scheduled']} scheduled prompts. Confidence: {full['confidence_score_pct']}%.*")

    return "\n".join(lines)


if __name__ == "__main__":
    run_date = sys.argv[1] if len(sys.argv) > 1 else datetime.utcnow().strftime("%Y-%m-%d")
    text = briefing_for(run_date)
    out_path = os.path.join(REPO, "metrics", f"briefing_{run_date}.md")
    with open(out_path, "w") as f:
        f.write(text)
    print(text)
    print(f"\n\nWritten to {out_path}")
