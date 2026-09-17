"""
Build the static dashboard: query the marts, write site/data.json, copy the page.
Runs after the pipeline passes, so a failed test means the old dashboard stays up.

  DATABASE_URL=... python dashboard/build.py   ->  site/index.html + site/data.json
"""
import datetime as dt
import decimal
import json
import os
import shutil
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from common.db import connect  # noqa: E402

QUERIES = {
    "summary": """
        select count(*) as opps,
               count(*) filter (where is_won) as won,
               count(*) filter (where is_closed) as closed,
               coalesce(sum(amount), 0) as pipeline_usd,
               coalesce(sum(amount) filter (where is_won), 0) as won_revenue_usd,
               min(created_at)::date as first_deal, max(created_at)::date as last_deal
        from marts.fct_opportunities""",
    "monthly": "select * from marts.mart_funnel_monthly order by month",
    "channels": "select * from marts.mart_channel_summary order by model, won_revenue_usd desc",
    "disagreement": "select * from marts.mart_model_disagreement order by swing desc",
    "truth": "select * from marts.mart_truth_evaluation order by model, true_share desc",
    "velocity": "select * from marts.mart_velocity order by opps desc",
    "retention": "select * from marts.mart_retention order by customers desc",
    "quality": "select check_name, description, value, threshold, direction, status from marts.mart_data_quality",
    "runs": """select run_id, started_at, finished_at, status, summary
               from ops.pipeline_runs order by run_id desc limit 14""",
}


def default(o):
    if isinstance(o, decimal.Decimal):
        return float(o)
    if isinstance(o, (dt.date, dt.datetime)):
        return o.isoformat()
    return str(o)


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    data = {}
    with connect(url) as conn, conn.cursor() as cur:
        for name, q in QUERIES.items():
            try:
                cur.execute(q)
            except Exception as e:  # e.g. no run log yet on a first local build
                conn.rollback()
                print(f"  ! {name}: {e}".strip())
                data[name] = []
                continue
            cols = [c.name for c in cur.description]
            data[name] = [dict(zip(cols, row)) for row in cur.fetchall()]
    data["summary"] = data["summary"][0] if data["summary"] else {}
    world = yaml.safe_load(open(os.path.join(ROOT, "config", "world.yml")))
    data["meta"] = {"company": world["company"]["name"], "pitch": world["company"]["pitch"],
                    "lookback_days": 90, "built_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")}
    data["metrics"] = yaml.safe_load(open(os.path.join(ROOT, "metrics", "metrics.yml")))["metrics"]

    out = os.path.join(ROOT, "site")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "data.json"), "w") as f:
        json.dump(data, f, default=default)
    shutil.copy(os.path.join(ROOT, "dashboard", "index.html"), os.path.join(out, "index.html"))
    open(os.path.join(out, ".nojekyll"), "w").close()
    print(f"Dashboard built -> site/ ({sum(len(v) for v in data.values() if isinstance(v, list))} rows)")


if __name__ == "__main__":
    main()
