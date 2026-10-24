"""Building + dorm lookup seed and walking-time helper.

SYNTHETIC/APPROXIMATE SEED: names are real-campus-style but every coordinate below is a
rough estimate and NEEDS HUMAN VERIFICATION before being trusted. If
fixtures/locations.csv exists it is loaded instead
(columns: code,name,lat,lon and optional kind = building|dorm; no kind => building).
"""
import csv
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


def load_locations() -> tuple[list[tuple], list[tuple], str]:
    """Returns (buildings, dorms, source) where source is 'csv' or 'synthetic-seed'."""
    if CSV_PATH.exists():
        b, d = [], []
        with CSV_PATH.open(newline="") as f:
            for r in csv.DictReader(f):
                row = (r["code"].strip(), r["name"].strip(), float(r["lat"]), float(r["lon"]))
                kind = (r.get("kind") or "").strip().lower()
                if kind != "dining":
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
    if CSV_PATH.exists():
        with CSV_PATH.open(newline="") as f:
            for r in csv.DictReader(f):
                if (r.get("kind") or "").strip().lower() == "dining":
                    out[r["code"].strip()] = (float(r["lat"]), float(r["lon"]))
    return out


def walking_seconds(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine distance (m) x 1.3 detour factor / 1.3 m/s walking speed."""
    p1, p2 = radians(lat1), radians(lat2)
    a = sin((p2 - p1) / 2) ** 2 + cos(p1) * cos(p2) * sin(radians(lon2 - lon1) / 2) ** 2
    meters = 2 * 6371000 * asin(sqrt(a))
    return meters * 1.3 / 1.3
