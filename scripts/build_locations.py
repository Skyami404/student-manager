#!/usr/bin/env python3
"""Build fixtures/locations.csv (code,name,lat,lon,kind,verified,check_link).
Buildings come from catalog.meetings (read-only). Geocoding is a ONE-TIME GUESS
via OpenStreetMap Nominatim. Every row must be verified by hand in Google Maps."""
import os, csv, time, pathlib, requests
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

FIX = pathlib.Path(__file__).resolve().parent.parent / "fixtures"
FIX.mkdir(exist_ok=True)
OUT = FIX / "locations.csv"

# Edit this list: dorm name -> search text. Add or remove to match your app.

DORMS = {
    "Warren Towers": "Warren Towers, 700 Commonwealth Ave",
    "Myles Standish Hall": "Myles Standish Hall, 610 Beacon St",
    "Student Village 1 (StuVi1)": "10 Buick St",
    "Student Village 2 (StuVi2)": "33 Harry Agganis Way",
    "Kilachand Hall": "Kilachand Hall, 91 Bay State Rd",
    "Claflin Hall": "Claflin Hall, 100 Bay State Rd",
}

# Codes to skip entirely
SKIP = {"NO", "MAS", "INS", "HOU", "EVN", "CTC", "ABG", "XBG", "RBN"}

# code -> street address. From memory: VERIFY on the map.
ADDRESSES = {
    "CAS": "725 Commonwealth Ave",
    "COM": "640 Commonwealth Ave",
    "CFA": "855 Commonwealth Ave",
    "CGS": "871 Commonwealth Ave",
    "SAR": "635 Commonwealth Ave",
    "STH": "745 Commonwealth Ave",
    "LAW": "765 Commonwealth Ave",
    "SSW": "264 Bay State Rd",
    "KHC": "91 Bay State Rd",
    "YAW": "100 Bay State Rd",
    "ENG": "110 Cummington Mall",
    "EPC": "750 Commonwealth Ave",
    "ERB": "44 Cummington Mall",
    "MCS": "111 Cummington Mall",
    "PSY": "64 Cummington Mall",
    "SOC": "100 Cummington Mall",
    "EMB": "15 Saint Mary's St",
    "PHO": "8 Saint Mary's St",
    "FLR": "808 Commonwealth Ave",
    "SHA": "928 Commonwealth Ave",
    "CLN": "900 Commonwealth Ave",
    "MET": "1010 Commonwealth Ave",
    "PTH": "949 Commonwealth Ave",
    "HIS": "226 Bay State Rd",
    "EGL": "236 Bay State Rd",
    "PLS": "232 Bay State Rd",
    "REL": "145 Bay State Rd",
    "AAS": "138 Mountfort St",
    "GDP": "53 Bay State Rd",
}

# Rough BU-area box (left, top, right, bottom) used to bias search and sanity-check results
VIEWBOX = (-71.135, 42.362, -71.085, 42.340)

def buildings_from_db():
    url = URL.create("postgresql+psycopg2",
        username=os.environ["DB_USER"], password=os.environ["DB_PASSWORD"],
        host=os.environ["DB_HOST"], port=int(os.environ.get("DB_PORT") or 5432),
        database=os.environ.get("DB_NAME") or "hackathon")
    eng = create_engine(url, connect_args={"sslmode": "require", "connect_timeout": 10})
    term = os.environ.get("CATALOG_TERM")
    q = """SELECT m.building_code, max(m.building) AS building, count(*) AS n
           FROM catalog.meetings m
           {join}
           WHERE m.building_code IS NOT NULL AND m.building_code <> ''
           GROUP BY 1 ORDER BY 3 DESC LIMIT 200"""
    join = ("JOIN catalog.sections s ON s.section_key = m.section_key "
            "JOIN catalog.courses c ON c.course_key = s.course_key AND c.term_code = :t") if term else ""
    with eng.connect() as c:
        rows = c.execute(text(q.format(join=join)), {"t": term} if term else {}).all()
    print(f"{len(rows)} building codes in the catalog" + (f" (term {term})" if term else " (all terms)"))
    return [(r.building_code, r.building or r.building_code, "building") for r in rows]

def geocode(query):
    """Try BU-biased search first, then a looser one. Returns (lat, lon) or None."""
    attempts = [
        {"q": f"{query}, Boston University, Boston, MA", "viewbox": ",".join(map(str, VIEWBOX)), "bounded": 1},
        {"q": f"{query}, Boston, MA"},
    ]
    for p in attempts:
        r = requests.get("https://nominatim.openstreetmap.org/search",
                         params={**p, "format": "json", "limit": 1},
                         headers={"User-Agent": "compass-hackathon-student"}, timeout=20).json()
        time.sleep(1.1)  # Nominatim limit: 1 request/second
        if r: return float(r[0]["lat"]), float(r[0]["lon"])
    return None

def in_box(lat, lon):
    return VIEWBOX[0] <= lon <= VIEWBOX[2] and VIEWBOX[3] <= lat <= VIEWBOX[1]

if __name__ == "__main__":
    # Keep rows you already verified by hand
    kept = {}
    if OUT.exists():
        for r in csv.DictReader(open(OUT)):
            if r.get("verified", "").upper() == "YES": kept[r["code"]] = r

    items = buildings_from_db() + [(n, q, "dorm") for n, q in DORMS.items()]
    rows = []
    for code, name, kind in items:
        if code in SKIP:
            print(f"SKIP  {code}"); continue
        if code in kept:
            rows.append(kept[code]); print(f"KEEP  {code} (verified)"); continue
        query = ADDRESSES.get(code) or DORMS.get(code, name)
        hit = geocode(query)
        lat, lon = (f"{hit[0]:.6f}", f"{hit[1]:.6f}") if hit else ("", "")
        status = "MISS " if not hit else ("FAR  " if not in_box(*hit) else "OK   ")
        print(f"{status}{code}: {name} -> {lat},{lon}")
        link = f"https://www.google.com/maps/search/?api=1&query={lat},{lon}" if hit else \
               f"https://www.google.com/maps/search/?api=1&query={query.replace(' ', '+')}+Boston+University"
        rows.append({"code": code, "name": name, "lat": lat, "lon": lon,
                     "kind": kind, "verified": "NO", "check_link": link})

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["code", "name", "lat", "lon", "kind", "verified", "check_link"])
        w.writeheader(); w.writerows(rows)

    miss = [r["code"] for r in rows if not r["lat"]]
    print(f"\nWrote {OUT} ({len(rows)} rows). MISS: {len(miss)} {miss[:15]}")
    print("FAR rows geocoded outside the BU-area box and are probably wrong.")
    print("Open each check_link, fix lat/lon, then set verified=YES.")