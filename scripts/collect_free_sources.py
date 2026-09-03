#!/usr/bin/env python3
"""
Collect the "genuinely free, no Claude needed" evidence sources:
  - evolutionnetzero.com sitemap inventory
  - Google News RSS (brand + topic + named-competitor queries)
  - GDELT DOC 2.0 API (with retry/backoff; marks itself unavailable rather
    than failing silently if GDELT rate-limits us)

This script has NO dependency on Claude/WebSearch and is safe to run from
GitHub Actions on a schedule, free, indefinitely. It does NOT attempt the
AI-answer audit (the core-15/weekly prompt bank) — that step requires
Claude's own web search and is run separately by a scheduled Claude Code
agent (see docs/CLAUDE_DAILY_AUDIT.md).

Never fabricates: a failed fetch is recorded under "unavailable_sources",
never silently dropped or replaced with a guess.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
OUT_DIR = os.path.join(REPO, "evidence", TODAY)

NEWS_QUERIES = [
    "\"Evolution NetZero\"",
    "hotel energy retrofit UK",
    "hotel HVAC optimisation",
    "hotel decarbonisation UK",
    "SensorFlow hotel",
    "Telnergy",
    "Envigilance hotel",
]

GDELT_QUERIES = ["\"Evolution NetZero\""]


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ENZ-AI-Visibility-Bot/1.0; free-tier RSS/sitemap reader)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def collect_sitemap():
    try:
        index = fetch("https://evolutionnetzero.com/sitemap_index.xml")
        sitemap_urls = re.findall(r"<loc>([^<]*)</loc>", index)
        pages, posts = [], []
        for sm_url in sitemap_urls:
            body = fetch(sm_url)
            locs = re.findall(r"<loc>([^<]*)</loc>", body)
            if "post-sitemap" in sm_url:
                posts.extend(locs)
            elif "page-sitemap" in sm_url:
                pages.extend(locs)
        return {
            "status": "ok",
            "collected_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": "evolutionnetzero.com sitemap_index.xml (Yoast SEO)",
            "collection_method": "direct HTTPS fetch, no auth",
            "pages_count": len(pages),
            "posts_count": len(posts),
            "pages": pages,
            "posts": posts,
        }
    except Exception as e:
        return {"status": "unavailable", "reason": str(e)}


def collect_news_rss():
    results, unavailable = [], []
    for q in NEWS_QUERIES:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-GB&gl=GB&ceid=GB:en"
        try:
            body = fetch(url)
            titles = re.findall(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", body)
            # first two titles are always the feed's own "<query> - Google News" / "Google News" — drop them
            article_titles = titles[2:]
            results.append({"query": q, "url": url, "result_count": len(article_titles), "titles": article_titles})
        except Exception as e:
            unavailable.append({"source": f"Google News RSS ({q})", "status": "unavailable this run", "reason": str(e)})
        time.sleep(1)
    return results, unavailable


def collect_gdelt():
    results, unavailable = [], []
    for q in GDELT_QUERIES:
        url = (
            "https://api.gdeltproject.org/api/v2/doc/doc?query="
            f"{urllib.parse.quote(q)}&mode=artlist&maxrecords=20&format=json&sort=datedesc"
        )
        ok = False
        last_err = None
        for attempt, delay in enumerate((5, 10, 20)):
            try:
                body = fetch(url)
                data = json.loads(body)
                results.append({"query": q, "url": url, "articles": data.get("articles", [])})
                ok = True
                break
            except json.JSONDecodeError:
                last_err = "GDELT returned a non-JSON rate-limit notice"
            except Exception as e:
                last_err = str(e)
            time.sleep(delay)
        if not ok:
            unavailable.append({
                "source": f"GDELT DOC 2.0 API ({q})",
                "status": "unavailable this run",
                "reason": last_err or "unknown",
                "action": "Retry next scheduled run. Do not substitute an estimate.",
            })
    return results, unavailable


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    unavailable_sources = []

    sitemap = collect_sitemap()
    if sitemap["status"] != "ok":
        unavailable_sources.append({"source": "evolutionnetzero.com sitemap", **sitemap})
    else:
        with open(os.path.join(OUT_DIR, "site_inventory.json"), "w") as f:
            json.dump(sitemap, f, indent=2)
        print(f"Sitemap: {sitemap['pages_count']} pages, {sitemap['posts_count']} posts")

    news_results, news_unavail = collect_news_rss()
    unavailable_sources.extend(news_unavail)

    gdelt_results, gdelt_unavail = collect_gdelt()
    unavailable_sources.extend(gdelt_unavail)

    news_doc = {
        "collected_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_engine": "Google News RSS",
        "collection_method": "direct RSS fetch, no auth, no key",
        "queries": news_results,
        "gdelt": gdelt_results,
        "unavailable_sources": unavailable_sources,
    }
    with open(os.path.join(OUT_DIR, "news_rss.json"), "w") as f:
        json.dump(news_doc, f, indent=2)

    print(f"News RSS: {len(news_results)} queries collected, {len(news_unavail)} unavailable")
    print(f"GDELT: {len(gdelt_results)} queries collected, {len(gdelt_unavail)} unavailable")
    if unavailable_sources:
        print(f"\n{len(unavailable_sources)} source(s) marked unavailable this run — see news_rss.json.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
