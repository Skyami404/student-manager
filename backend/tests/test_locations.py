"""Location classification: approximate vs unknown, driven by a throwaway locations.csv."""
import pytest

import locations
from locations import LocationInfo, walking_seconds

CSV = """code,name,lat,lon,kind,verified
CDS,Computing & Data Sciences,42.3503,-71.1033,building,YES
SCI,Metcalf Science Center,42.3503,-71.1002,building,NO
CAS,College of Arts & Sciences,,,building,NO
INS,BUMC Instructional Building,,,building,NO
NO,No Room - in-person,,,building,NO
"""


@pytest.fixture()
def info(tmp_path, monkeypatch):
    csv = tmp_path / "locations.csv"
    csv.write_text(CSV)
    monkeypatch.setattr(locations, "CSV_PATH", csv)
    _, _, source = locations.load_locations()
    assert source == "csv"
    buildings, _, _ = locations.load_locations()
    return LocationInfo({code: (lat, lon) for code, _, lat, lon in buildings})


@pytest.mark.parametrize("code, room, status", [
    ("CDS", "101", "ok"),              # in the table and verified
    ("SCI", "1", "approximate"),       # in the table but marked verified = NO
    ("CAS", "5", "approximate"),       # row without coordinates is treated as missing
    ("ZZZ", "1", "approximate"),       # not in the table at all
    ("INS", "1", "unknown"),           # medical campus (BUMC)
    ("NO", "x", "unknown"),            # the "No Room" placeholder building
    ("CDS", "No Room", "unknown"),     # "No Room" given as the room
    (None, "1", "unknown"),            # no building listed
    ("", "1", "unknown"),
])
def test_location_status(info, code, room, status):
    assert info.status(code, room) == status


def test_unknown_locations_explain_themselves(info):
    assert "medical campus" in info.unknown_reason("INS", "1")
    assert "No Room" in info.unknown_reason("NO", "1")
    assert "no building" in info.unknown_reason(None, "1")
    assert info.unknown_reason("CDS", "101") is None


def test_walking_time_is_distance_times_detour_over_speed():
    # the formula is haversine x 1.3 / 1.3 m/s, so seconds are numerically the straight-line metres
    one_degree_lat = walking_seconds(42.0, -71.0, 43.0, -71.0)
    assert 111_000 < one_degree_lat < 111_400
    assert walking_seconds(42.35, -71.1, 42.35, -71.1) == 0
