import os, re, sys, json, socket, decimal, datetime as dt, pathlib
from sqlalchemy import create_engine, inspect, MetaData, Table, select, func, text
from sqlalchemy.engine import URL

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX, SEED = ROOT / "fixtures", ROOT / "backend" / "cache_seed"
FIX.mkdir(exist_ok=True); SEED.mkdir(parents=True, exist_ok=True)

HOST = os.environ["DB_HOST"]
USER, PW, DBNAME = os.environ.get("DB_USER", ""), os.environ.get("DB_PASSWORD", ""), os.environ.get("DB_NAME", "")
TRIM_N, SEED_LIMIT, MAX_TABLES = 40, 20000, 40

# Tables worth dumping (matched on table name)
INCLUDE = r"course|section|class|meeting|sched|subject|term|session|hub|attribute|building|room|location|facility|instruct|offering|campus|college|dept|department|prereq|requisite|component|crosslist"
# Never dump tables that look like student/personal records
BLOCK = r"(^|_)(student|person|people|user|account|grade|transcript|applicant|auth|login|password|token|audit|enroll\w*)s?(_|$)"
ALLOW = [t for t in os.environ.get("ALLOW_TABLES", "").split(",") if t]
# Redact personal-looking columns
REDACT = r"email|phone|ssn|dob|birth|passw|token|secret|address|netid|buid|emplid"
SYSTEM = {"information_schema", "mysql", "performance_schema", "sys", "pg_catalog", "pg_toast"}

# After reading catalog_schema.json, restrict big tables to the current term, e.g.
# FILTERS = {"sections": "term_code = '2026FALL'"}   (raw SQL WHERE, your own words)
FILTERS = {}

def pick_engine():
    e = os.environ.get("DB_ENGINE", "auto").lower()
    if e in ("mysql", "postgres"): return e
    for eng, port in (("mysql", 3306), ("postgres", 5432)):
        try:
            socket.create_connection((HOST, port), 6).close(); print("port open:", port); return eng
        except OSError: print("no connection on", port)
    sys.exit("Cannot reach the DB host. Are you on the BU network/VPN? Ask the hackathon organizers.")

def js(o):
    if isinstance(o, (dt.datetime, dt.date, dt.time)): return o.isoformat()
    if isinstance(o, decimal.Decimal): return float(o)
    if isinstance(o, (bytes, bytearray, memoryview)): return "<binary>"
    return str(o)

eng = pick_engine()
driver, default_port = ("mysql+pymysql", 3306) if eng == "mysql" else ("postgresql+psycopg2", 5432)
url = URL.create(driver, username=USER, password=PW, host=HOST,
                 port=int(os.environ.get("DB_PORT") or default_port),
                 database=DBNAME or (None if eng == "mysql" else "postgres"))
args = {"connect_timeout": 10}
if os.environ.get("DB_SSL", "1") == "1":
    if eng == "mysql": args["ssl"] = {"check_hostname": False}
    else: args["sslmode"] = "require"
engine = create_engine(url, connect_args=args)

insp = inspect(engine)
want = os.environ.get("DB_SCHEMAS")
if want: schemas = want.split(",")
elif eng == "mysql" and DBNAME: schemas = [DBNAME]
else: schemas = [s for s in insp.get_schema_names() if s not in SYSTEM]
print("schemas:", schemas)

selected, all_names = [], []
for s in schemas:
    names = insp.get_table_names(schema=s) + insp.get_view_names(schema=s)
    all_names += [f"{s}.{n}" for n in names]
    for n in names:
        if n in ALLOW or (re.search(INCLUDE, n, re.I) and not re.search(BLOCK, n, re.I)):
            selected.append((s, n))
print(f"\n{len(all_names)} tables/views total:\n  " + ", ".join(all_names[:200]))
if not selected:
    sys.exit("\nNo tables matched INCLUDE. Edit INCLUDE in this script using the names above.")
if len(selected) > MAX_TABLES:
    print(f"\n{len(selected)} matched; keeping the first {MAX_TABLES}. Narrow INCLUDE."); selected = selected[:MAX_TABLES]
print("\nDumping:", ", ".join(f"{s}.{n}" for s, n in selected))

schema_doc, multi = {}, len(schemas) > 1
with engine.connect() as conn:
    try:
        conn.execute(text("SET SESSION TRANSACTION READ ONLY" if eng == "mysql"
                          else "SET default_transaction_read_only = on"))
    except Exception as e: print("note: could not set read-only session:", e)
    for s, n in selected:
        key = f"{s}.{n}" if multi else n
        try:
            cols = insp.get_columns(n, schema=s)
            doc = {"columns": [{"name": c["name"], "type": str(c["type"]), "nullable": c.get("nullable")} for c in cols],
                   "primary_key": insp.get_pk_constraint(n, schema=s).get("constrained_columns"),
                   "foreign_keys": [{"cols": f["constrained_columns"], "ref": f"{f.get('referred_table')}.{f['referred_columns']}"}
                                    for f in insp.get_foreign_keys(n, schema=s)]}
            t = Table(n, MetaData(), autoload_with=engine, schema=s)
            doc["row_count"] = conn.execute(select(func.count()).select_from(t)).scalar()
            q = select(t)
            if n in FILTERS: q = q.where(text(FILTERS[n]))
            rows = []
            for r in conn.execute(q.limit(SEED_LIMIT)):
                d = dict(r._mapping)
                rows.append({k: ("[REDACTED]" if re.search(REDACT, k, re.I) else v) for k, v in d.items()})
        except Exception as e:
            conn.rollback(); print(f"SKIP {key}: {str(e)[:150]}"); continue
        schema_doc[key] = doc
        (SEED / f"catalog_{key}.json").write_text(json.dumps(rows, default=js))
        k = TRIM_N
        while True:
            body = json.dumps(rows[:k], indent=1, default=js)
            if len(body) < 50_000 or k <= 3: break
            k //= 2
        (FIX / f"catalog_{key}.json").write_text(body)
        print(f"  {key}: {doc['row_count']} rows total, {len(rows)} in seed, {k} in fixture ({len(body)/1024:.0f} KB)")

(FIX / "catalog_schema.json").write_text(json.dumps(schema_doc, indent=1))
print("\nwrote fixtures/catalog_schema.json  <- Kiro's main reference for the catalog")

cols = {c["name"].lower() for d in schema_doc.values() for c in d["columns"]}
print("\n=== Feature check (column names) ===")
for label, pat in {"meeting times": r"start|end|time|days|meet", "building/room": r"build|bldg|room|facility|location",
                   "credits": r"credit|units", "Hub units": r"hub", "seats": r"seat|capacity|enrl|enroll",
                   "prerequisites": r"prereq|requisite", "term": r"term|semester", "instructor": r"instruct"}.items():
    m = sorted(c for c in cols if re.search(pat, c))[:6]
    print(f"{'OK ' if m else 'NO '} {label:15} {', '.join(m)}")