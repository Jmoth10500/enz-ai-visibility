# Claude daily AI-visibility audit — routine instructions

This file is the prompt for the scheduled Claude Code cloud agent that runs
the AI-answer half of the audit. It exists as a separate routine from the
GitHub Actions workflow because **only Claude's own tools can query Claude's
web search** — there is no free, headless, public API for "what does an AI
answer engine say" that a plain script could call instead. This is the one
part of the system that genuinely requires Claude to run it.

Repo: `~/Projects/enz-ai-visibility` (also mirrored to GitHub — see README).

## What to do, every time this runs

1. `cd ~/Projects/enz-ai-visibility && git pull` to make sure you're working
   from the latest state (the free-source GitHub Action may have committed
   since your last run).
2. Read `prompts/prompt_bank.json` → `core_15`.
3. For each of the 15 core prompts, run it through WebSearch **exactly as
   written** — do not add "Evolution NetZero", "ENZ", "evolutionnetzero.com"
   or any leading language to the query. The prompt bank is neutral by
   design; keep it that way.
4. For each result, build one evidence record with every field the schema
   in `evidence/2026-09-03/core_15.json` demonstrates: id, query,
   funnel_stage, date_time_utc, source_engine ("Claude Web Search"),
   result_type, enz_mentioned, enz_recommendation_position,
   enz_url_cited, competitors_mentioned (name + url + role), sentiment_context,
   evidence_excerpt (≤25 words, a real quote — never paraphrase into a
   stronger claim than the source supports), confidence, notes.
5. **Never fabricate.** If a query returns nothing useful, or WebSearch
   errors, record it plainly (`enz_mentioned: false`, empty
   `competitors_mentioned`, a note saying what happened) — do not invent a
   plausible-sounding result.
6. Write the day's file to `evidence/<YYYY-MM-DD>/core_15.json` in the same
   shape as `evidence/2026-09-03/core_15.json` (copy that file's structure).
7. On the **first run of each ISO week** (Monday), also generate and run the
   wider weekly variant set: combine `prompts/prompt_bank.json` →
   `weekly_variant_axes` with the 20 subjects listed in the original brief,
   one axis at a time (never stack more than two axes into one prompt —
   it should still read as a real question a buyer would ask). Aim for
   40–60 prompts. Save as `evidence/<date>/weekly_variants.json`.
8. Run `python3 scripts/score.py` to recompute metrics from all evidence
   collected so far (this also picks up whatever the free-source GitHub
   Action already collected today).
9. Run `python3 scripts/daily_briefing.py <date>` to generate the plain-
   English briefing.
10. Update the published dashboard Artifact:
    - Read the artifact (`Artifact action: "read"` with its saved URL — see
      `docs/ARTIFACT_URL.txt`).
    - Merge in today's `metrics/<date>.json`, `metrics/history.json`, and
      the day's evidence files (via the artifact's own data mechanism, or by
      republishing the HTML with the new data baked in — whichever the
      dashboard's current build uses; check the dashboard's own comments).
    - Publish. Do not touch design/layout unless asked — this step is a
      data refresh only.
11. Commit and push: `git add -A && git commit -m "Daily audit: <date>" && git push`.
12. Post a short summary back to the user: what changed, today's single best
    action, and a link to the refreshed dashboard. Use the briefing file's
    content — don't re-write it from scratch.

## Failure handling

If any step fails (WebSearch error, git push rejected, artifact publish
conflict), **stop and report the failure plainly** rather than partially
completing and claiming success. The previous day's dashboard and evidence
must stay intact and valid — never leave the repo or the published
dashboard in a half-updated state.

## Setting up the schedule

This routine is meant to be run by `CronCreate` / the `schedule` skill in
Claude Code, once, by Jonathan — not something this file does on its own.
Suggested cadence: once daily, a time with low sandbox contention (evening
UK time worked well for the seed run). The GitHub Action
(`.github/workflows/free_sources_daily.yml`) runs independently at 06:00 UTC
and does not depend on this routine, so the two can run at different times
without conflict — this routine's `git pull` step picks up whatever the
Action already committed.
