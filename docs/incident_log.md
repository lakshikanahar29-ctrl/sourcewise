# Incident log

Real problems hit while building and running Sourcewise. Newest first.
Format: date · what broke · how I found out · fix · what now prevents it.

## 2026-09-17 · Second pipeline run failed at the load step
- **What broke:** The loader drops and recreates each raw table. On the second run Postgres refused:
  `cannot drop table raw.adroll_daily because other objects depend on it` — the dbt staging views sit on the raw tables.
- **How I found out:** The run stopped with a non-zero exit code on the load step.
- **Fix:** If the export has the same columns, the loader now `TRUNCATE`s and reloads in place. It only rebuilds
  (with `CASCADE`) when an export's columns actually change, and it prints a warning when that happens.
- **Prevention:** Every run records its steps and status in `ops.pipeline_runs`; a failed step exits non-zero and
  posts to Slack.

## 2026-09-17 · Gross revenue retention came out negative for one channel
- **What broke:** `(start − contraction − churn) / start` went below zero for google_ads, because a customer expanded
  and then churned at the higher MRR.
- **How I found out:** Sanity check of `mart_retention` output (GRR of −0.044 is impossible).
- **Fix:** GRR now caps each customer at their starting MRR. Recorded as v2 in `metrics/metrics.yml`.

## 2026-09-17 · Retargeting looked 5× more valuable than it was designed to be (generator bug)
- **What broke:** Planted truth said retargeting has almost no effect, yet its true incremental revenue came out at
  ~$71K. Retargeting clicks were refreshing the "recent visitor" audience, so a visitor was retargeted forever.
- **How I found out:** The ground-truth table disagreed with the configured lift.
- **Fix:** Retargeting audiences are now built only from non-retargeting visits.
