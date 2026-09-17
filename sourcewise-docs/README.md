# Sourcewise

**Which GTM source actually produces revenue — and how much does the answer depend on how you count?**

Sourcewise loads a year and a half of GTM activity for a fictional B2B SaaS company (Quillstack, AI contract review),
stitches every touch to a person, an account and a deal, credits revenue under five attribution models, and checks
those models against a planted ground truth.

> All data is synthetic, generated from `config/world.yml`. No real companies, people or revenue.

## Pipeline

```
generator (Python, seeded)  →  raw.* in Postgres  →  dbt: staging → identity → touchpoints → attribution → marts
                                                         └── 75 tests on every run; a failure stops the run and alerts Slack
```

| Layer | What it does |
|---|---|
| `generator/` | Simulates 600 accounts / ~2,400 people day by day. Writes exports shaped like HubSpot, GA4, LinkedIn Ads, Google Ads (micros), AdRoll, Smartlead, Clay, the Reply Bot, the Voice Agent (IST timestamps) and Stripe. Adds real mess: missing UTMs, duplicate gmail contacts, deals without contacts, skipped and re-opened stages, a renamed channel. |
| `loader/` | Lands every CSV as text in `raw.*`. |
| `dbt/models/staging` | Types, cleans and classifies each source. |
| `dbt/models/intermediate` | Identity resolution (phone merge, cookie → person, Clay name + domain match), one unified touchpoint table, the 90-day deal window. |
| `dbt/models/marts` | `fct_attribution` (long format), channel performance, model disagreement, funnel, velocity, retention, data quality, truth evaluation. |
| `dashboard/` | `build.py` queries the marts into `site/data.json`; `index.html` is a dependency-free dashboard (5 tabs). Published to GitHub Pages only after all tests pass. |
| `reverse_etl/` | Pushes first-touch channel, attributed pipeline and a source-quality score onto HubSpot company records. Dry run by default, matches on domain (so re-runs never duplicate), writes only changed values, logs every write to `ops.crm_writes`. |
| `metrics/metrics.yml` | Definition, version and changelog for every number. |
| `docs/` | Architecture diagram, incident log (what broke, how I found out, what changed), write-up and Loom script. |

## Attribution models

first touch · last non-direct touch · linear · W-shaped (30/30/30 + 10) · time decay (7-day half-life).
Weights and the lookback window are dbt vars in `dbt/dbt_project.yml`.

Tests that must pass on every run:
- credit per deal sums to exactly 1.0 under every model
- credited won revenue reconciles to CRM won revenue, per model, to the cent
- no touch after the deal was created gets credit
- every deal appears in every model (deals with no touch get an explicit `unattributed` row)

## Planted ground truth

The generator gives each channel a hidden effect on buying intent. After the real run it re-simulates the world with
each channel switched off (12 replicate worlds) and records the drop in won revenue: that channel's true incremental
revenue. Only `mart_truth_evaluation` reads it, to score how close each attribution model gets.

## Run it locally

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=postgresql://user:password@localhost:5432/sourcewise
python run_pipeline.py              # generate → load → dbt build (≈40s)
python run_pipeline.py --skip-truth # faster: skips the counterfactual runs
python dashboard/build.py && python -m http.server -d site 8000   # dashboard at localhost:8000
```

## Nightly run

`.github/workflows/nightly.yml` runs the pipeline every day at 02:00 IST, then rebuilds the dashboard and publishes it to
GitHub Pages. If any test fails, the publish step never runs and yesterday's dashboard stays up.
Repository secrets: `DATABASE_URL` (Supabase session-pooler connection string), optionally `SLACK_WEBHOOK_URL` and `HUBSPOT_TOKEN`.
Each run is recorded in `ops.pipeline_runs`.

## Status

- [x] Generator, loader, dbt models, 5 attribution models, tests, data quality, truth evaluation
- [x] Pipeline runner, run log, Slack alert, nightly workflow file
- [x] Dashboard on GitHub Pages (overview, channels, model disagreement, GTM systems, data health)
- [x] Reverse ETL to HubSpot (runs in the nightly workflow when `HUBSPOT_TOKEN` is set)
- [x] Architecture diagram, write-up and Loom script (`docs/`)
