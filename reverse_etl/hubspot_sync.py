"""
Reverse ETL: push Sourcewise results onto HubSpot company records, so reps see the
answer in the CRM instead of in a dashboard.

Three properties per company:
  sourcewise_first_touch_channel   the channel that started the relationship
  sourcewise_attributed_pipeline   W-shaped credited pipeline, USD
  sourcewise_source_quality_score  0-100 score for the sourcing channel (see metrics.yml)

Rules this job follows:
  * dry run by default; --live is required to write anything
  * idempotent: companies are matched on domain, so re-running never creates duplicates
  * only changed values are sent
  * every write is logged to ops.crm_writes with the run's timestamp

  HUBSPOT_TOKEN=pat-... DATABASE_URL=... python reverse_etl/hubspot_sync.py          # dry run
  HUBSPOT_TOKEN=pat-... DATABASE_URL=... python reverse_etl/hubspot_sync.py --live   # writes
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from common.db import connect  # noqa: E402

API = "https://api.hubapi.com"
PROPERTIES = [
    {"name": "sourcewise_first_touch_channel", "label": "Sourcewise: first touch channel",
     "type": "string", "fieldType": "text"},
    {"name": "sourcewise_attributed_pipeline", "label": "Sourcewise: attributed pipeline (USD)",
     "type": "number", "fieldType": "number"},
    {"name": "sourcewise_source_quality_score", "label": "Sourcewise: source quality score",
     "type": "number", "fieldType": "number"},
]

# Company-level payload. Score: 60% how often that first-touch channel wins,
# 40% how much won revenue it is credited with (W-shaped). Both ranked 0-1 across channels.
SQL = """
with credited as (
    select o.domain,
           sum(a.credited_pipeline) filter (where a.model = 'w_shaped') as attributed_pipeline
    from marts.fct_attribution a
    join marts.fct_opportunities o using (deal_id)
    group by 1
),
channel_score as (
    select v.first_touch_channel as channel,
           percent_rank() over (order by coalesce(v.win_rate, 0))        as win_rank,
           percent_rank() over (order by coalesce(s.won_revenue_usd, 0)) as rev_rank
    from marts.mart_velocity v
    left join marts.mart_channel_summary s
      on s.channel = v.first_touch_channel and s.model = 'w_shaped'
),
company as (
    select distinct on (o.domain)
           o.domain, o.company_name, o.first_touch_channel, o.created_at
    from marts.fct_opportunities o
    order by o.domain, o.created_at desc
)
select c.domain,
       c.company_name,
       coalesce(c.first_touch_channel, 'unattributed')                   as first_touch_channel,
       round(coalesce(cr.attributed_pipeline, 0))::int                   as attributed_pipeline,
       round(100 * (0.6 * coalesce(cs.win_rank, 0) + 0.4 * coalesce(cs.rev_rank, 0)))::int as source_quality_score
from company c
left join credited cr using (domain)
left join channel_score cs on cs.channel = c.first_touch_channel
order by attributed_pipeline desc
limit %(limit)s
"""


def api(token, method, path, payload=None, retries=4):
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(API + path, data=body, method=method,
                                 headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read() or "{}")
        except urllib.error.HTTPError as e:
            text = e.read().decode()[:400]
            if e.code in (429, 502, 503, 504) and attempt < retries - 1:
                wait = 2 ** attempt
                print(f"  HubSpot {e.code}, retrying in {wait}s")
                time.sleep(wait)
                continue
            raise RuntimeError(f"HubSpot {method} {path} -> {e.code}: {text}") from None


def ensure_properties(token, live):
    existing = {p["name"] for p in api(token, "GET", "/crm/v3/properties/companies")["results"]}
    for p in PROPERTIES:
        if p["name"] in existing:
            continue
        if not live:
            print(f"  [dry run] would create property {p['name']}")
            continue
        api(token, "POST", "/crm/v3/properties/companies", {**p, "groupName": "companyinformation"})
        print(f"  created property {p['name']}")


def read_existing(token, domains):
    """Current record id + values in HubSpot, keyed by domain, for companies that already exist."""
    out = {}
    props = [p["name"] for p in PROPERTIES]
    for i in range(0, len(domains), 100):
        chunk = domains[i:i + 100]
        res = api(token, "POST", "/crm/v3/objects/companies/search", {
            "filterGroups": [{"filters": [{"propertyName": "domain", "operator": "IN", "values": chunk}]}],
            "properties": ["domain"] + props, "limit": 100})
        for r in res.get("results", []):
            d = (r["properties"].get("domain") or "").lower()
            if d and d not in out:  # first record wins if a domain is duplicated in the CRM
                out[d] = {"id": r["id"], **{k: r["properties"].get(k) for k in props}}
    return out


def changed(row, current):
    if current is None:
        return True
    return (current.get("sourcewise_first_touch_channel") != row["first_touch_channel"]
            or str(current.get("sourcewise_attributed_pipeline") or "") not in (str(row["attributed_pipeline"]), str(float(row["attributed_pipeline"])))
            or str(current.get("sourcewise_source_quality_score") or "") not in (str(row["source_quality_score"]), str(float(row["source_quality_score"]))))


def sw_props(r):
    return {
        "sourcewise_first_touch_channel": r["first_touch_channel"],
        "sourcewise_attributed_pipeline": r["attributed_pipeline"],
        "sourcewise_source_quality_score": r["source_quality_score"],
    }


def log_writes(url, rows, live):
    with connect(url) as conn, conn.cursor() as cur:
        cur.execute("""create schema if not exists ops;
                       create table if not exists ops.crm_writes (
                         id bigserial primary key, written_at timestamptz default now(),
                         system text, object text, domain text, payload jsonb, mode text)""")
        for r in rows:
            cur.execute("insert into ops.crm_writes (system, object, domain, payload, mode) values ('hubspot','company',%s,%s,%s)",
                        (r["domain"], json.dumps(r), "live" if live else "dry_run"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="actually write to HubSpot (default: dry run)")
    ap.add_argument("--limit", type=int, default=200, help="companies to sync, largest attributed pipeline first")
    args = ap.parse_args()

    url, token = os.environ.get("DATABASE_URL"), os.environ.get("HUBSPOT_TOKEN")
    if not url:
        sys.exit("DATABASE_URL is not set")

    with connect(url) as conn, conn.cursor() as cur:
        cur.execute(SQL, {"limit": args.limit})
        cols = [c.name for c in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
    print(f"{len(rows)} companies to consider (top {args.limit} by attributed pipeline)")

    if not token:
        print("HUBSPOT_TOKEN is not set: showing the first 5 records that would be written\n")
        for r in rows[:5]:
            print("  ", r)
        log_writes(url, rows, live=False)
        return

    ensure_properties(token, args.live)
    current = read_existing(token, [r["domain"] for r in rows])
    todo = [r for r in rows if changed(r, current.get(r["domain"]))]
    print(f"{len(current)} companies already in HubSpot · {len(todo)} need an update · {len(rows) - len(todo)} unchanged")

    if not args.live:
        for r in todo[:5]:
            print("  [dry run] would write", r)
        print("\nDry run only. Re-run with --live to write.")
        log_writes(url, todo, live=False)
        return

    # HubSpot only allows upsert-by-property when that property is unique in the portal, and
    # `domain` is not. So: update the companies that already exist by their record id, and
    # create the rest. Matching still happens on domain, so re-runs never duplicate.
    updates = [r for r in todo if r["domain"] in current]
    creates = [r for r in todo if r["domain"] not in current]
    written = 0
    for i in range(0, len(updates), 100):
        chunk = updates[i:i + 100]
        api(token, "POST", "/crm/v3/objects/companies/batch/update", {
            "inputs": [{"id": current[r["domain"]]["id"], "properties": sw_props(r)} for r in chunk]})
        written += len(chunk)
        print(f"  updated {written}/{len(updates)}")
    made = 0
    for i in range(0, len(creates), 100):
        chunk = creates[i:i + 100]
        api(token, "POST", "/crm/v3/objects/companies/batch/create", {
            "inputs": [{"properties": {"domain": r["domain"], "name": r["company_name"], **sw_props(r)}} for r in chunk]})
        made += len(chunk)
        print(f"  created {made}/{len(creates)}")
    written += made
    log_writes(url, todo, live=True)
    print(f"Done: {len(updates)} companies updated, {made} created in HubSpot.")


if __name__ == "__main__":
    main()
