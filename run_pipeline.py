"""
One command for the whole nightly run:
  generate world -> load raw -> dbt build (models + tests) -> record the run -> alert on failure

  DATABASE_URL=postgresql://... python run_pipeline.py            # full run
  python run_pipeline.py --skip-truth                              # faster, keeps last truth file

Optional: SLACK_WEBHOOK_URL posts a message when a run fails (and a short summary when it passes).
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from urllib.parse import urlparse, unquote

import psycopg2

ROOT = os.path.dirname(os.path.abspath(__file__))


def db_env(url: str) -> dict:
    u = urlparse(url)
    return {"SW_DB_HOST": u.hostname, "SW_DB_PORT": str(u.port or 5432), "SW_DB_USER": unquote(u.username or ""),
            "SW_DB_PASSWORD": unquote(u.password or ""), "SW_DB_NAME": u.path.lstrip("/") or "postgres",
            "SW_DB_SSLMODE": "require" if u.hostname not in ("localhost", "127.0.0.1") else "prefer"}


def step(name, cmd, env, log):
    t0 = time.time()
    print(f"\n=== {name}: {' '.join(cmd)}", flush=True)
    p = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    print(p.stdout[-4000:])
    if p.returncode != 0:
        print(p.stderr[-4000:], file=sys.stderr)
    log.append({"step": name, "seconds": round(time.time() - t0, 1), "ok": p.returncode == 0})
    return p


def notify(text):
    hook = os.environ.get("SLACK_WEBHOOK_URL")
    if not hook:
        return
    req = urllib.request.Request(hook, data=json.dumps({"text": text}).encode(), headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:  # alerting must never crash the run
        print(f"slack notify failed: {e}")


def record_run(url, started, status, log, summary):
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        cur.execute("""create schema if not exists ops;
                       create table if not exists ops.pipeline_runs (
                         run_id bigserial primary key, started_at timestamptz, finished_at timestamptz,
                         status text, steps jsonb, summary jsonb, git_sha text)""")
        cur.execute("insert into ops.pipeline_runs (started_at, finished_at, status, steps, summary, git_sha) values (%s, now(), %s, %s, %s, %s)",
                    (started, status, json.dumps(log), json.dumps(summary), os.environ.get("GITHUB_SHA")))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-truth", action="store_true")
    ap.add_argument("--end-date", default=None)
    args = ap.parse_args()

    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    env = {**os.environ, **db_env(url), "DBT_PROFILES_DIR": os.path.join(ROOT, "dbt")}
    started = datetime.now(timezone.utc)
    log, summary = [], {}

    gen = [sys.executable, "generator/generate.py"] + (["--skip-truth"] if args.skip_truth else []) + \
          (["--end-date", args.end_date] if args.end_date else [])
    ok = step("generate", gen, env, log).returncode == 0
    ok = ok and step("load", [sys.executable, "loader/load.py"], env, log).returncode == 0
    if ok:
        p = step("dbt_build", ["dbt", "build", "--project-dir", "dbt"], env, log)
        ok = p.returncode == 0
        tail = [l for l in p.stdout.splitlines() if "Done. PASS=" in l]
        summary["dbt"] = tail[-1].split("Done. ")[-1] if tail else "no summary"

    status = "success" if ok else "failed"
    try:
        with psycopg2.connect(url) as conn, conn.cursor() as cur:
            cur.execute("select count(*), count(*) filter (where is_won), coalesce(sum(amount) filter (where is_won), 0) from marts.fct_opportunities")
            summary["opps"], summary["won"], summary["won_revenue_usd"] = [float(x) for x in cur.fetchone()]
            cur.execute("select count(*) from marts.mart_data_quality where status = 'warn'")
            summary["data_quality_warnings"] = cur.fetchone()[0]
    except Exception as e:
        summary["summary_error"] = str(e)[:200]
    record_run(url, started, status, log, summary)

    msg = f"Sourcewise nightly run {status.upper()} | {summary.get('dbt', '')} | steps: " + \
          ", ".join(f"{s['step']} {'ok' if s['ok'] else 'FAILED'} ({s['seconds']}s)" for s in log)
    print("\n" + msg)
    notify(msg)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
