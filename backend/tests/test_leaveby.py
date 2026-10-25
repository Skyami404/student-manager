"""Leave-by helpers: on-time probability, risk levels and the stored-schedule round trip."""
import pytest

import leaveby


def test_walk_probability_is_bounded_and_rises_with_slack():
    values = [leaveby.p_walk_ok(slack, 8) for slack in (0, 4, 8, 10, 15, 30)]
    assert values == sorted(values)
    assert 0 < min(values) and max(values) < 1  # never 0% or 100%
    assert leaveby.p_walk_ok(-3, 8) == leaveby.p_walk_ok(0, 8)


@pytest.mark.parametrize("p, level", [(0.98, "green"), (0.85, "green"), (0.84, "amber"), (0.5, "amber"), (0.49, "red")])
def test_risk_levels(p, level):
    assert leaveby.risk_level(p) == level


def test_transition_risk_marks_unknown_locations_as_not_assessed():
    rows = [
        {"day": "Mon", "gap_minutes": 10, "walk_minutes": 4, "from_building": "CDS", "to_building": "SCI", "approximate": False},
        {"day": "Mon", "gap_minutes": 10, "walk_minutes": None, "from_building": "INS", "to_building": "SCI",
         "location_unknown": True, "unknown_why": "INS is on the medical campus"},
    ]
    leaveby.add_transition_risk(rows)
    assert rows[0]["risk"] in {"green", "amber", "red"} and 0 < rows[0]["p_on_time"] < 1
    assert rows[1]["risk"] == "unknown" and rows[1]["p_on_time"] is None
    assert "not assessed" in rows[1]["risk_why"] and "medical campus" in rows[1]["risk_why"]


def test_schedule_ids_ignore_section_order_and_depend_on_the_sections():
    assert leaveby.schedule_id(["1", "2"], "Warren Towers") == leaveby.schedule_id(["2", "1"], "Warren Towers")
    assert leaveby.schedule_id(["1", "2"], "Warren Towers") != leaveby.schedule_id(["1", "3"], "Warren Towers")


def test_stored_schedules_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(leaveby, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(leaveby, "STORE", tmp_path / "schedules.json")
    schedule = {"sections": [{"id": "1", "course_code": "X", "days": ["Mon"], "start": "09:00", "end": "09:50"}]}
    sid = leaveby.save_schedule(schedule, "Warren Towers", "fast")
    entry = leaveby.load_schedule(sid)
    assert entry["schedule"] == schedule and entry["dorm_id"] == "Warren Towers" and entry["walking_pace"] == "fast"
    assert leaveby.load_schedule("does-not-exist") is None
