#!/usr/bin/env python3
"""Read-only: show term columns/values in terms, sections, meetings."""
import os, re
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL

url = URL.create("postgresql+psycopg2",
    username=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT") or 5432),
    database=os.environ.get("DB_NAME") or "hackathon")
engine = create_engine(url, connect_args={"sslmode": "require", "connect_timeout": 10})
insp = inspect(engine)

where = {}
for s in insp.get_schema_names():
    if s in ("information_schema", "pg_catalog", "pg_toast"): continue
    for n in insp.get_view_names(schema=s) + insp.get_table_names(schema=s):
        if n in ("terms", "sections", "meetings"): where[n] = s

cols = {}
for n, s in where.items():
    cols[n] = [c["name"] for c in insp.get_columns(n, schema=s)]
    print(f"\n== {s}.{n} columns:\n   {', '.join(cols[n])}")

with engine.connect() as conn:
    if "terms" in where:
        print("\n== terms rows (up to 30):")
        for r in conn.execute(text(f'SELECT * FROM {where["terms"]}.terms LIMIT 30')):
            print("  ", dict(r._mapping))
    for n in ("sections", "meetings"):
        tc = [c for c in cols.get(n, []) if re.search("term|semester", c, re.I)]
        if not tc: print(f"\n{n}: no term-like column (filter through sections)"); continue
        for c in tc:
            print(f"\n== {n}.{c}: values and row counts")
            q = f'SELECT "{c}", count(*) FROM {where[n]}.{n} GROUP BY 1 ORDER BY 1 DESC LIMIT 15'
            for r in conn.execute(text(q)): print("  ", tuple(r))

if "sections" in cols and "meetings" in cols:
    shared = sorted(set(cols["sections"]) & set(cols["meetings"]))
    print("\ncolumns shared by sections and meetings (likely join key):", shared)