#!/usr/bin/env python3
"""
Assemble the dashboard HTML by substituting real evidence/metrics JSON and
the ENZ logo (as a base64 data URI) into the template. Run this any time the
evidence changes, then publish the output file as the Artifact.
"""
import base64
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")
LOGO_PATH = "/Users/jonathannuttall/Library/Mobile Documents/com~apple~CloudDocs/Evolution Netzero/AI B.R.A.I.N/11_ASSETS/images/Logo/EZ Logo V4 Trans only.png"
OUT_PATH = os.path.join(REPO, "dist", "enz_ai_visibility_dashboard.html")


def latest(run_date=None):
    if run_date is None:
        dates = sorted(os.listdir(os.path.join(REPO, "evidence")))
        run_date = dates[-1]
    return run_date


def load(path):
    with open(path) as f:
        return json.load(f)


def main():
    run_date = latest(sys.argv[1] if len(sys.argv) > 1 else None)
    print(f"Building dashboard for {run_date}")

    metrics = load(os.path.join(REPO, "metrics", f"{run_date}.json"))
    core15 = load(os.path.join(REPO, "evidence", run_date, "core_15.json"))
    news = load(os.path.join(REPO, "evidence", run_date, "news_rss.json"))
    site = load(os.path.join(REPO, "evidence", run_date, "site_inventory.json"))
    promptbank = load(os.path.join(REPO, "prompts", "prompt_bank.json"))
    history = load(os.path.join(REPO, "metrics", "history.json"))

    with open(LOGO_PATH, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode("ascii")

    with open(TEMPLATE) as f:
        html = f.read()

    html = html.replace("{{LOGO_B64}}", logo_b64)
    html = html.replace("{{METRICS_JSON}}", json.dumps(metrics))
    html = html.replace("{{CORE15_JSON}}", json.dumps(core15))
    html = html.replace("{{NEWS_JSON}}", json.dumps(news))
    html = html.replace("{{SITE_JSON}}", json.dumps(site))
    html = html.replace("{{PROMPTBANK_JSON}}", json.dumps(promptbank))
    html = html.replace("{{HISTORY_JSON}}", json.dumps(history))

    with open(OUT_PATH, "w") as f:
        f.write(html)

    print(f"Wrote {OUT_PATH} ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
