"""Calendar export: weekly events, leave-by alarms (only when a walking time exists) and file format."""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import ics

NOW = datetime(2026, 10, 26, 8, 0, tzinfo=ZoneInfo("America/New_York"))  # a Monday
BUILDINGS = {"CDS": (42.3503, -71.1033), "SCI": (42.3503, -71.1002)}


def section(sid, building, days=("Mon", "Wed"), start="10:00", end="10:50"):
    return {"id": sid, "course_code": f"CAS {sid[0].upper()}X 100", "section_label": "A1", "days": list(days), "start": start, "end": end,
            "building_code": building, "room": "101" if building else None, "seats_open": None, "component": "lecture"}


def build(sections, **kw):
    entry = {"schedule": {"sections": sections}, "dorm_id": None, "walking_pace": "normal"}
    raw = ics.build(entry, BUILDINGS, {}, include_meals=False, weeks=10, now=NOW, **kw)
    return raw, re.sub(r"\r\n[ \t]", "", raw)  # (as written, with folded lines joined)


def events(unfolded):
    return unfolded.split("BEGIN:VEVENT")[1:]


def test_weekly_events_with_leave_by_alarms():
    raw, text = build([section("a1", "CDS"), section("b1", "SCI", start="11:00", end="11:50")])
    assert text.startswith("BEGIN:VCALENDAR") and text.rstrip().endswith("END:VCALENDAR")
    assert len(events(text)) == 4  # two sections x two days
    assert all("RRULE:FREQ=WEEKLY;COUNT=10;BYDAY=" in e for e in events(text))
    assert text.count("BEGIN:VALARM") == 4
    assert "X-WR-CALNAME:Compass schedule\r\n" in text


def test_no_alarm_for_a_class_with_no_walking_time():
    _, text = build([section("a1", None)])  # no building listed: location unknown
    (event,) = events(text)[:1]
    assert "VALARM" not in event
    assert "location unknown" in event


def test_synthetic_catalog_is_labelled_in_the_file():
    _, text = build([section("a1", "CDS")], synthetic=True)
    assert "sample data\\, synthetic" in text.lower()  # the comma is escaped as \, in iCalendar text


def test_file_format_rules_are_respected():
    raw, _ = build([section("a1", "CDS")])
    assert raw.count("\r\n") == raw.count("\n")  # CRLF line endings only
    assert max(len(line.encode()) for line in raw.split("\r\n")) <= 75  # long lines are folded
