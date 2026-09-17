"""
Load generated CSV exports into Postgres, exactly as a raw landing zone would:
every column arrives as text and gets typed later in dbt staging.

Tables are replaced on every run (full refresh). Uses DATABASE_URL, e.g.
postgresql://user:pass@host:5432/db  (Supabase: Project Settings -> Database -> URI)
"""
import csv
import glob
import os
import sys
import time

import psycopg2
from psycopg2 import sql

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_dir(cur, folder, schema):
    cur.execute(sql.SQL("create schema if not exists {}").format(sql.Identifier(schema)))
    total = 0
    for path in sorted(glob.glob(os.path.join(folder, "*.csv"))):
        table = os.path.splitext(os.path.basename(path))[0]
        with open(path, newline="") as f:
            header = next(csv.reader(f))
        ident = sql.Identifier(schema, table)
        cur.execute("select array_agg(column_name::text order by ordinal_position) from information_schema.columns "
                    "where table_schema = %s and table_name = %s and column_name <> '_loaded_at'", (schema, table))
        existing = cur.fetchone()[0]
        if existing == header:
            # same shape: truncate in place so the dbt staging views that sit on top keep working
            cur.execute(sql.SQL("truncate table {}").format(ident))
        else:
            # new or changed export shape: rebuild (CASCADE drops dependent views; dbt recreates them)
            cols = sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c)) for c in header)
            cur.execute(sql.SQL("drop table if exists {} cascade").format(ident))
            cur.execute(sql.SQL("create table {} ({}, _loaded_at timestamptz default now())").format(ident, cols))
            if existing:
                print(f"  ! {schema}.{table}: column set changed, table rebuilt")
        with open(path) as f:
            copy = sql.SQL("copy {} ({}) from stdin with (format csv, header true, null '')").format(
                ident, sql.SQL(", ").join(sql.Identifier(c) for c in header))
            cur.copy_expert(copy.as_string(cur), f)
        cur.execute(sql.SQL("select count(*) from {}").format(ident))
        n = cur.fetchone()[0]
        total += n
        print(f"  {schema}.{table:30s} {n:>8,}")
    return total


def main():
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set")
    t0 = time.time()
    with psycopg2.connect(url) as conn, conn.cursor() as cur:
        n = load_dir(cur, os.path.join(ROOT, "data", "raw"), "raw")
        load_dir(cur, os.path.join(ROOT, "data", "truth"), "truth")
    print(f"Loaded {n:,} raw rows in {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
