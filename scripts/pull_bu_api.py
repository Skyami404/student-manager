"""Discover endpoints from the BU gateway's OpenAPI spec, pull transit + dining.
Full -> backend/cache_seed/, trimmed -> fixtures/."""
import os, re, json, time, pathlib
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
FIX, SEED = ROOT / "fixtures", ROOT / "backend" / "cache_seed"
FIX.mkdir(exist_ok=True); SEED.mkdir(parents=True, exist_ok=True)

BASE = os.environ.get("BU_BASE", "https://public.api-nonprod.bu.edu").rstrip("/")
KEY, TOKEN = os.environ.get("BU_API_KEY", ""), os.environ.get("BU_TOKEN", "")
AUTH = os.environ.get("BU_AUTH", "x-api-key")
SPEC_URL = os.environ.get("BU_SPEC_URL", "")   # set if auto-discovery fails
TRIM_N, MAX_PULLS = 40, 25

TOPICS = {
    "transit": r"transit|bus|stop|route|arriv|predict|vehicle|shuttle|alert|timetable",
    "dining":  r"dining|menu|hall|meal|food|nutrition|allerg",
}
# Endpoints that need parameters: add after reading fixtures/_bu_endpoints.txt
# ("name", "/path", {"param": "value"})
MANUAL = []

def auth():
    if TOKEN: return {"Authorization": f"Bearer {TOKEN}"}, {}
    if not KEY or AUTH == "none": return {}, {}
    if AUTH == "bearer": return {"Authorization": f"Bearer {KEY}"}, {}
    if AUTH.startswith("query:"): return {}, {AUTH.split(":", 1)[1]: KEY}
    return {AUTH: KEY}, {}

def find_spec():
    cands = [SPEC_URL] if SPEC_URL else [BASE + p for p in (
        "/openapi.json", "/swagger.json", "/v3/api-docs", "/api-docs",
        "/docs/openapi.json", "/docs/swagger.json")]
    h, p = auth()
    for u in cands:
        try: r = requests.get(u, headers=h, params=p, timeout=20)
        except requests.RequestException: continue
        if r.ok:
            try: j = r.json()
            except ValueError: continue
            if "paths" in j: print("spec found:", u); return j
    return None

def api_base(spec):
    if spec.get("servers"):
        u = spec["servers"][0].get("url", "").rstrip("/")
        return u if u.startswith("http") else BASE + u
    return BASE + spec.get("basePath", "").rstrip("/")

def resolve(spec, p):
    if "$ref" in p:
        node = spec
        for part in p["$ref"].lstrip("#/").split("/"): node = node.get(part, {})
        return node
    return p

def classify(path, op):
    t = " ".join([path, op.get("summary") or "", (op.get("description") or "")[:200],
                  " ".join(op.get("tags") or [])])
    for topic, pat in TOPICS.items():
        if re.search(pat, t, re.I): return topic

def trim(obj, n):
    c = [(None, obj)] if isinstance(obj, list) else \
        [(k, v) for k, v in obj.items() if isinstance(v, list)] if isinstance(obj, dict) else []
    if not c: return obj
    k, lst = max(c, key=lambda x: len(x[1]))
    if len(lst) <= n: return obj
    return lst[:n] if k is None else {**obj, k: lst[:n]}

def save(name, data):
    (SEED / f"{name}.json").write_text(json.dumps(data))
    p = FIX / f"{name}.json"
    n = TRIM_N
    while True:
        s = json.dumps(trim(data, n), indent=1)
        if len(s) < 50_000 or n <= 3: break
        n //= 2
    p.write_text(s)
    print(f"      saved {name}.json ({len(s)/1024:.0f} KB, {n} records max)")

def fetch(url, params):
    h, p = auth()
    try: r = requests.get(url, params={**params, **p}, headers=h, timeout=30)
    except requests.RequestException as e: print("FAIL", url, e); return None
    print(r.status_code, url)
    if not r.ok: print("      ", r.text[:200]); return None
    try: return r.json()
    except ValueError: print("      not JSON, skipped"); return None

if __name__ == "__main__":
    spec = find_spec()
    if not spec and not MANUAL:
        raise SystemExit("No OpenAPI spec found. Open the docs page, DevTools > Network, "
                         "find the .json spec URL, then: export BU_SPEC_URL=<that url>")
    root, pulls, lines = (api_base(spec) if spec else BASE), [], []
    for path, item in (spec or {}).get("paths", {}).items():
        op = item.get("get")
        if not op: continue
        params = [resolve(spec, p) for p in item.get("parameters", []) + op.get("parameters", [])]
        req = [p["name"] for p in params if p.get("required") and p.get("in") == "query"]
        topic = classify(path, op)
        needs = "{" in path or bool(req)
        lines.append(f"GET {path}  [{topic or '-'}]" + (f"  NEEDS: {path if '{' in path else ''} {req}" if needs else ""))
        if topic and not needs: pulls.append((topic, path))
    (FIX / "_bu_endpoints.txt").write_text("\n".join(lines))
    print(f"{len(lines)} GET endpoints listed in fixtures/_bu_endpoints.txt")

    for topic, path in pulls[:MAX_PULLS]:
        d = fetch(root + path, {})
        if d is not None: save(f"{topic}_{re.sub(r'[^a-z0-9]+', '_', path.lower()).strip('_')}", d)
        time.sleep(0.3)
    for name, path, params in MANUAL:
        d = fetch(root + path, params)
        if d is not None: save(name, d)

    print("\nTopic endpoints that still need params (add to MANUAL):")
    for l in lines:
        if "NEEDS" in l and not l.endswith("[-]") and "[-]" not in l: print("  ", l)

    leaked = [f for f in list(FIX.glob("*")) + list(SEED.glob("*"))
              if f.is_file() and any(s and s in f.read_text() for s in (KEY, TOKEN))]
    print("\nSECRET FOUND IN:" if leaked else "\nsecret scan: clean", *leaked)