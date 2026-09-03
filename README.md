# Evolution NetZero — AI Visibility Intelligence

An independent, self-hosted audit of how visible **Evolution NetZero**
(evolutionnetzero.com) is when people research hotel/PBSA/care home/office
energy retrofit, HVAC optimisation and decarbonisation partners — measured
against a fixed, neutral prompt bank, using only free sources.

This is **not** connected to HubSpot. It does not measure market share,
revenue, traffic or leads. It measures whether ENZ shows up, where, next to
whom, and cited from where — with every number traceable to a dated,
auditable evidence file.

## What's actually in this repo

```
prompts/prompt_bank.json         The fixed neutral prompt bank (core 15 + weekly variant axes)
evidence/<YYYY-MM-DD>/           Raw, dated, auditable evidence — never edited after the fact
  core_15.json                     Today's core-15 AI-answer audit (Claude Web Search)
  news_rss.json                    Google News RSS + GDELT evidence (free, no key)
  site_inventory.json              evolutionnetzero.com sitemap snapshot
metrics/<YYYY-MM-DD>.json        Computed scores for that day (see Scoring model below)
metrics/history.json             Append-only time series, used for 7/30/90-day trends
metrics/briefing_<date>.md       Plain-English daily briefing
scripts/
  score.py                         Computes all 10 metrics from evidence — never estimates
  daily_briefing.py                Generates the daily briefing, with real change thresholds
  collect_free_sources.py          Headless, free-only collector (sitemap + News RSS + GDELT)
  build_farm_territories.py        (unrelated — ignore, artifact of a different project)
docs/CLAUDE_DAILY_AUDIT.md       Instructions for the Claude-run half of the daily audit
.github/workflows/               GitHub Action for the free-source half (runs without Claude)
.env.example                     Optional connected-source config — see below
```

## Why there are *two* daily jobs, not one

The brief asks for "genuinely free data sources... tools already included
with Claude" run on a repeatable daily schedule. That splits cleanly into
two halves with two different honest automation paths:

1. **The AI-answer audit** (does ENZ get mentioned when someone asks an AI
   these 15 neutral questions) genuinely requires Claude's own web search.
   There is no free public API for "ask an AI assistant a question and read
   its answer" that a plain script could call — so this half is run by a
   **scheduled Claude Code agent** (see `docs/CLAUDE_DAILY_AUDIT.md`), which
   is the free mechanism Claude Code itself provides for exactly this.
2. **Everything else that's genuinely a public API or feed** — the
   evolutionnetzero.com sitemap, Google News RSS, GDELT — needs no Claude
   access at all, so it runs as a plain **GitHub Actions** cron job
   (`.github/workflows/free_sources_daily.yml`), free, indefinitely, with no
   dependency on this session staying alive.

Both halves write into the same `evidence/<date>/` folder and the same
`scripts/score.py` recomputes metrics from whatever's there — so either job
running alone still produces a valid (if partial) day, and coverage is
reported honestly (`prompt_coverage_pct`) rather than assumed complete.

## Honesty rules this system actually enforces in code, not just in prose

- `scripts/score.py` refuses to compute anything from zero records
  (`SystemExit` rather than a fabricated 0%).
- A metric with insufficient data (e.g. third-party validation rate, before
  review sources are collected) is written as `null` with a note explaining
  why — never silently coerced to 0.
- Trends (`compute_trends`) are `available: false` with a stated reason
  until there's genuinely a prior run old enough to compare against. Day 1
  has no trends. That's correct, not a bug.
- `daily_briefing.py` uses fixed change thresholds (see `THRESHOLDS` in the
  script) and explicitly says "nothing material changed today" when nothing
  crosses them — no manufactured daily drama.
- `collect_free_sources.py` records a failed source under
  `unavailable_sources` with the real error, and does not substitute an
  estimate. GDELT rate-limited the first run; it's recorded as unavailable,
  not guessed.
- The confidence score is capped at 85% when only one search engine/backend
  was used (currently: Claude's own web search only) — see
  `engine_diversity_cap` in `score.py`. It will only reach higher once a
  second independent source (e.g. a connected GSC/Bing account) is added.

## Scoring model

All 10 metrics from the brief are computed in `scripts/score.py`, each
documented inline with what it means and what it explicitly does *not* mean
(none of them are "market share", "revenue", "traffic" or "leads"). See the
dashboard's "Methodology & limitations" tab for the plain-English version of
each, and the **Metric explainer** section for the reference dashboard
comparison.

## Optional connected sources (GSC / GA4 / Bing)

Copy `.env.example` → `.env`, fill in only what you connect. The core audit
runs identically with none of these connected — they add an additional,
clearly-separate "conventional search evidence" section, never blended into
the independent AI-visibility score (the brief is explicit about this: AI
visibility and conventional search visibility are displayed as separate
evidence groups, always).

## Running it locally

```bash
cd ~/Projects/enz-ai-visibility
python3 scripts/collect_free_sources.py     # sitemap + news RSS + GDELT (no Claude needed)
python3 scripts/score.py                    # recompute metrics from all evidence on disk
python3 scripts/daily_briefing.py $(date -u +%Y-%m-%d)
```

The AI-answer half (`core_15.json`) is produced by a Claude Code session
following `docs/CLAUDE_DAILY_AUDIT.md` — it isn't a script you can run
outside Claude, by design (see above).

## Deployment / scheduling setup (one-time)

1. **GitHub Action**: already committed. Enable it by pushing this repo to
   GitHub (already done — see repo remote) and confirming Actions are
   enabled in the repo's Settings → Actions.
2. **Claude Code scheduled agent**: run `/schedule` (or ask Claude to set
   one up) pointing at `docs/CLAUDE_DAILY_AUDIT.md`'s instructions, once
   daily. This is the step that needs a one-time decision from you — see
   the chat for the exact command used.
3. **Optional connected sources**: fill in `.env` locally, or add the same
   values as GitHub Actions repo secrets (`GSC_SITE_URL`,
   `GSC_SERVICE_ACCOUNT_JSON`, etc.) if you want the Action to pull them too.

## Dashboard

Published as a Claude Artifact (see `docs/ARTIFACT_URL.txt` for the live
link once published). It reads `metrics/history.json` and the day's
`metrics/<date>.json` + evidence files, bundled in at publish time — every
number on the dashboard has a "view evidence" path back to the exact JSON
record that produced it (Raw Evidence Viewer tab).

## Known limitations (also shown in-dashboard)

- The AI-answer audit currently uses **one** search backend (Claude's own
  web search). It is *not* a query to ChatGPT, Gemini, Copilot or
  Perplexity specifically — no free API access exists to those. The
  dashboard labels this "Claude Web Search" throughout, never
  "AI engines" generically.
- Day-1 baseline: 7/30/90-day trends need real history to exist first.
  They'll start populating from the second daily run onward.
- Third-party validation rate is not yet computed — it needs a defined set
  of "third-party review/discussion sources" to check against, which is a
  follow-on build, not guessed at here.
- GSC/GA4/Bing are unconnected until you provide credentials — their
  sections show "not connected", not zero.
