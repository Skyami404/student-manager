#!/usr/bin/env python3
"""Read-only: which schemas/views can this user actually SELECT from?"""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

url = URL.create("postgresql+psycopg2",
    username=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
    host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT") or 5432),
    database=os.environ.get("DB_NAME") or "hackathon")
engine = create_engine(url, connect_args={"sslmode": "require", "connect_timeout": 10})

Q = """
SELECT n.nspname AS schema, c.relname AS name,
       CASE c.relkind WHEN 'v' THEN 'view' WHEN 'r' THEN 'table' WHEN 'm' THEN 'matview' ELSE c.relkind::text END AS kind,
       has_schema_privilege(n.nspname, 'USAGE') AS schema_usage,
       has_table_privilege(c.oid, 'SELECT') AS can_select
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind IN ('r','v','m','f')
  AND n.nspname NOT IN ('pg_catalog','information_schema','pg_toast')
ORDER BY 1, 2
"""
with engine.connect() as conn:
    print("search_path:", conn.execute(text("SHOW search_path")).scalar())
    print("\nschema.name  kind  schema_usage  can_select")
    ok = []
    for r in conn.execute(text(Q)):
        flag = "OK " if (r.schema_usage and r.can_select) else "NO "
        print(f"{flag}{r.schema}.{r.name}  {r.kind}  {r.schema_usage}  {r.can_select}")
        if r.schema_usage and r.can_select: ok.append((r.schema, r.name))
    print("\nReadable:", ok or "NOTHING")
    for s, n in ok:
        try:
            cols = conn.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema=:s AND table_name=:n ORDER BY ordinal_position"), {"s": s, "n": n}).scalars().all()
            print(f"\n== {s}.{n}: {', '.join(cols)}")
        except Exception as e:
            conn.rollback(); print(f"{s}.{n}: {str(e)[:100]}")