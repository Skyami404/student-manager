"""Building + dorm lookup seed and walking-time helper.

SYNTHETIC/APPROXIMATE SEED: names are real-campus-style but every coordinate below is a
rough estimate and NEEDS HUMAN VERIFICATION before being trusted. If
fixtures/locations.csv exists it is loaded instead
(columns: code,name,lat,lon and optional kind = building|dorm|dining, verified = YES/NO, campus = medical).
Rows without numeric lat/lon are skipped. Unverified rows, buildings missing from the table, and any
section the app cannot place (no building, "No Room", medical campus) are handled by LocationInfo below.
"""
import csv
import re
from math import asin, cos, radians, sin, sqrt
from pathlib import Path

CSV_PATH = Path(__file__).resolve().parent.parent / "fixtures" / "locations.csv"

# (code, name, lat, lon)
BUILDINGS = [
    ("CAS", "College of Arts & Sciences", 42.3505, -71.1054),
    ("CDS", "Computing & Data Sciences", 42.3503, -71.1033),
    ("CGS", "College of General Studies", 42.3509, -71.1105),
    ("COM", "College of Communication", 42.3506, -71.1027),
    ("EPC", "Engineering Product Innovation Center", 42.3497, -71.1050),
    ("GSU", "George Sherman Union", 42.3511, -71.1085),
    ("KCB", "Kilachand Hall", 42.3493, -71.1010),
    ("MCS", "Math & Computer Science", 42.3490, -71.1027),
    ("PHO", "Photonics Center", 42.3487, -71.1038),
    ("SAR", "Sargent College", 42.3510, -71.1022),
    ("SCI", "Metcalf Science Center", 42.3503, -71.1002),
    ("SMG", "Questrom School of Business", 42.3505, -71.1013),
    ("STH", "School of Theology", 42.3510, -71.1060),
    ("LAW", "School of Law", 42.3513, -71.1067),
    ("MUG", "Mugar Memorial Library", 42.3508, -71.1087),
    ("FIT", "Fitness & Recreation Center", 42.3527, -71.1163),
    ("AGG", "Agganis Arena", 42.3532, -71.1155),
    ("CFA", "College of Fine Arts", 42.3510, -71.1100),
    ("STO", "Stone Science Building", 42.3502, -71.1040),
    ("ENG", "College of Engineering", 42.3488, -71.1020),
    ("SSW", "School of Social Work", 42.3490, -71.1090),
    ("SPH", "School of Public Health (Medical Campus)", 42.3360, -71.0720),
    ("LSE", "Life Science & Engineering Building", 42.3496, -71.1043),
    ("CIL", "Center for Integrated Life Sciences", 42.3490, -71.1050),
    ("MAR", "Marsh Chapel", 42.3509, -71.1058),
    ("TSC", "Tsai Performance Center", 42.3503, -71.1043),
    ("SED", "School of Education", 42.3507, -71.1067),
    ("MET", "Metropolitan College", 42.3512, -71.1066),
    ("PSY", "Psychological & Brain Sciences", 42.3492, -71.1045),
]

DORMS = [
    ("WAR", "Warren Towers", 42.3516, -71.1048),
    ("SV1", "Student Village I", 42.3530, -71.1172),
    ("SV2", "Student Village II", 42.3523, -71.1180),
    ("MYL", "Myles Standish Hall", 42.3484, -71.1011),
    ("CLF", "Claflin Hall", 42.3515, -71.1135),
    ("RCH", "Rich Hall", 42.3515, -71.1145),
    ("DAN", "Danielsen Hall", 42.3490, -71.0980),
    ("SHI", "Shields Hall", 42.3512, -71.1128),
]


# ---- location classification (used by scoring, risk, leave-by, meals, Hub, ICS) -------------------
# "ok"          building is in the table and its coordinates are verified (fixtures/locations.csv)
# "approximate" building missing from the table, or its coordinates are unverified (the synthetic seed):
#               a walking time is still estimated but flagged approximate
# "unknown"     no building, "No Room", or medical campus: NO walking time; excluded from transition risk
MEDICAL_CAMPUS_CODES = {"SPH"}  # seed; fixtures/locations.csv may add rows with campus=medical
_MEDICAL_NAME = re.compile(r"\bbumc\b|medical", re.I)
_NO_ROOM = re.compile(r"^\s*no[\s_-]*room", re.I)


def _csv_rows() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(newline="") as f:
        return list(csv.DictReader(f))


def _has_coords(r: dict) -> bool:
    try:
        float(r["lat"])
        float(r["lon"])
        return True
    except (KeyError, TypeError, ValueError):
        return False


def _is_verified(r: dict) -> bool:
    return (r.get("verified") or "1").strip().lower() not in ("0", "false", "no", "n")


def using_csv() -> bool:
    return CSV_PATH.exists()


class LocationInfo:
    """Classifies a (building_code, room) pair. coords = the buildings table as {code: (lat, lon)}.
    From fixtures/locations.csv it also learns which codes are medical-campus or "No Room" placeholders
    (even when they have no coordinates) and which rows are verified."""

    def __init__(self, coords: dict):
        self.coords = coords
        rows = [r for r in _csv_rows() if (r.get("kind") or "building").strip().lower() == "building"]
        self.verified = {r["code"].strip() for r in rows if _is_verified(r) and _has_coords(r)}
        self.verified_dorms = {r["code"].strip() for r in _csv_rows()
                               if (r.get("kind") or "").strip().lower() == "dorm" and _is_verified(r) and _has_coords(r)}
        self.medical = set(MEDICAL_CAMPUS_CODES)
        self.no_room: set[str] = set()
        names = {c: n for c, n, *_ in BUILDINGS}
        for r in rows:
            code, name = r["code"].strip(), (r.get("name") or "")
            names[code] = name
            if (r.get("campus") or "").strip().lower() == "medical":
                self.medical.add(code)
            if _NO_ROOM.match(name):
                self.no_room.add(code)
        self.medical |= {c for c, n in names.items() if _MEDICAL_NAME.search(n)}

    def unknown_reason(self, code: str | None, room: str | None = None) -> str | None:
        if not code or not code.strip():
            return "no building is listed"
        if code in self.no_room or _NO_ROOM.match(code) or (room and _NO_ROOM.match(room)):
            return "the section has no room assigned (\"No Room\")"
        if code in self.medical:
            return f"{code} is on the medical campus, which has no walking estimate"
        return None

    def status(self, code: str | None, room: str | None = None) -> str:
        if self.unknown_reason(code, room):
            return "unknown"
        if code not in self.coords or code not in self.verified:
            return "approximate"
        return "ok"


def load_locations() -> tuple[list[tuple], list[tuple], str]:
    """Returns (buildings, dorms, source) where source is 'csv' or 'synthetic-seed'.
    CSV rows without numeric lat/lon are left out of the table on purpose: such buildings are then
    "missing" and get an approximate walking time instead of a made-up location."""
    if CSV_PATH.exists():
        b, d = [], []
        for r in _csv_rows():
            kind = (r.get("kind") or "").strip().lower()
            if kind == "dining" or not _has_coords(r):
                continue
            row = (r["code"].strip(), r["name"].strip(), float(r["lat"]), float(r["lon"]))
            (d if kind == "dorm" else b).append(row)
        return b, d, "csv"
    return BUILDINGS, DORMS, "synthetic-seed"


# Dining hall coordinates (the dining API has addresses only). APPROXIMATE / SYNTHETIC SEED:
# keys are the gateway's dining location ids. Needs human verification, like the buildings above.
DINING = {
    "marciano": (42.3492, -71.1008),  # 100 Bay State Road
    "warren": (42.3516, -71.1048),    # 700 Commonwealth Ave (same site as the Warren Towers dorm seed)
    "west": (42.3518, -71.1175),      # 275 Babcock Street
}


def dining_coords() -> dict[str, tuple[float, float]]:
    """fixtures/locations.csv rows with kind=dining override the seed (columns code,name,lat,lon,kind)."""
    out = dict(DINING)
    for r in _csv_rows():
        if (r.get("kind") or "").strip().lower() == "dining" and _has_coords(r):
            out[r["code"].strip()] = (float(r["lat"]), float(r["lon"]))
    return out


def walking_seconds(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance (m) x 1.3 detour factor / 1.3 m/s walking speed."""
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    meters = 2 * 6371000 * asin(sqrt(a))
    return meters * 1.3 / 1.3
