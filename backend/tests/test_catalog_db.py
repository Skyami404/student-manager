"""Catalog adapter: Hub/prerequisite parsing and the filtering rules, on hand-made rows (no database)."""
import pytest

from clients import catalog_db as cd


@pytest.mark.parametrize("text, expected", [
    ("Effective Fall 2018, this course fulfills a single unit in each of the following BU Hub areas: "
     "Social Inquiry 1, Quantitative Reasoning 2, Writing- Intensive Course.",
     ["Social Inquiry I", "Quantitative Reasoning II", "Writing-Intensive Course"]),
    # one real area name contains commas, so the list cannot simply be split on ","
    ("fulfills a single unit in the following BU Hub areas: Writing, Research, and Inquiry, Oral and/or Signed Communication.",
     ["Writing, Research, and Inquiry", "Oral and/or Signed Communication"]),
    ("fulfills a single unit in the BU Hub area of Teamwork/Collaboration.", ["Teamwork/Collaboration"]),
    ("in each of the following BU Hub areas Quantitative Reasoning II, Critical Thinking.", ["Quantitative Reasoning II", "Critical Thinking"]),
    ("fulfills a single unit in the following Hub area: Digital Medial Expression.", ["Digital/Multimedia Expression"]),
    # the latest "Effective <term> <year>" sentence wins, whatever order the sentences appear in
    ("Effective Spring 2021, in the following BU Hub area: Ethical Reasoning. Effective Fall 2018, in the following BU Hub area: Critical Thinking.",
     ["Ethical Reasoning"]),
    ("Effective Fall 2018, in the following BU Hub area: Critical Thinking. Effective Spring 2021, in each of the following BU Hub areas: Ethical Reasoning, Aesthetic Exploration.",
     ["Ethical Reasoning", "Aesthetic Exploration"]),
    # things that mention "Hub" but are not an area list
    ("Co-requisite: HUB CC 234. - supports a trip", []),
    ("Effective Fall 2026 this course no longer carries HUB units.", []),
    ("A plain description.", []),
    ("", []),
    (None, []),
])
def test_parse_hub_units(text, expected):
    assert cd.parse_hub_units(text) == expected


@pytest.mark.parametrize("text, expected", [
    ("Undergraduate Prerequisites: CAS PY 105 or equivalent. - The sequence...", ["CAS PY 105 or equivalent."]),
    ("Prerequisite: consent of department. Co-requisite: HUB CC 234. - This course", ["consent of department. Co-requisite: HUB CC 234."]),
    ("Prerequisites: QSTSM 131", ["QSTSM 131"]),
    ("Undergraduate Prerequisites: None - blah", []),
    ("Graduate Prerequisites: consent of instructor - x", []),  # graduate-only text is not an undergraduate prerequisite
    ("A plain description.", []),
    (None, []),
])
def test_parse_prerequisites(text, expected):
    assert cd.parse_prerequisites(text) == expected


def test_course_code_and_time_formatting():
    assert cd.format_code("CASPH", "CASPH251") == "CAS PH 251"
    assert cd.format_code("SDMOS", "SDMOS521AS") == "SDM OS 521AS"  # suffixes are kept
    assert cd.format_code("ODD", "ODD1") == "ODD1"  # unexpected shapes pass through untouched
    assert cd.hhmm("15.30.00.000000") == "15:30"
    assert cd.hhmm("9:05:00") == "09:05"
    assert cd.hhmm("") is None and cd.hhmm("garbage") is None


def _course(key, code, desc=""):
    return {"course_key": key, "display_code": code, "subject": code[:5], "title": f"Title {code}", "description": desc}


def _section(skey, ckey, number, label, credits, section_type):
    return {"section_key": skey, "course_key": ckey, "class_number": number, "section": label, "credits": credits, "section_type": section_type}


def _meeting(skey, day, start, end, building="", room=""):
    return {"section_key": skey, "day": day, "start_time": start, "end_time": end, "building_code": building, "room": room}


def test_build_snapshot_filtering_rules():
    courses = [
        _course("c1", "CASAA101", "Undergraduate Prerequisites: CAS ZZ 100. - Effective Fall 2020, this course fulfills a single unit "
                                  "in each of the following BU Hub areas: Critical Thinking, Ethical Reasoning."),
        _course("c2", "CASBB200"),   # lecture with two meeting slots
        _course("c3", "CASCC300"),   # weekend only
        _course("c4", "CASDD400"),   # half credit
        _course("c5", "CASEE500"),   # lab has no meeting time, so the course would silently lose its lab
        _course("c6", "CASFF600"),   # "Independent" is an ordinary class type in this catalog
        _course("c7", "CASGG700"),   # directed study
        _course("c8", "CASHH800"),   # its two slots overlap each other
    ]
    sections = [
        _section("s1", "c1", "1001", "A1", "4", "Lecture"), _section("s2", "c1", "1002", "B1", "4", "Discussion"),
        _section("s3", "c1", "1003", "B2", "4", "Discussion"),  # unscheduled sibling: dropped, course stays
        _section("s4", "c2", "1004", "A1", "4", "Lecture"),
        _section("s5", "c3", "1005", "A1", "4", "Lecture"),
        _section("s6", "c4", "1006", "A1", "0.5", "Lecture"),
        _section("s7", "c5", "1007", "A1", "4", "Lecture"), _section("s8", "c5", "1008", "L1", "4", "Laboratory"),
        _section("s9", "c6", "1009", "A1", "4", "Independent"),
        _section("s10", "c7", "1010", "A1", "4", "Directed Study"),
        _section("s11", "c8", "1011", "A1", "4", "Lecture"),
    ]
    meetings = [
        _meeting("s1", "MWF", "09.05.00.000000", "09.55.00.000000", "CAS", "101"),
        _meeting("s2", "T", "10.10.00.000000", "11.00.00.000000"),
        _meeting("s4", "TR", "14.00.00.000000", "15.15.00.000000", "SCI", "1"),
        _meeting("s4", "R", "18.30.00.000000", "20.30.00.000000"),
        _meeting("s5", "S", "10.00.00.000000", "11.00.00.000000"),
        _meeting("s6", "M", "10.00.00.000000", "10.50.00.000000"),
        _meeting("s7", "M", "11.00.00.000000", "11.50.00.000000"),
        _meeting("s9", "F", "13.25.00.000000", "14.15.00.000000"),
        _meeting("s10", "W", "09.05.00.000000", "09.55.00.000000"),
        _meeting("s11", "MW", "10.00.00.000000", "11.00.00.000000"), _meeting("s11", "W", "10.30.00.000000", "11.30.00.000000"),
    ]
    listed, secs, stats = cd.build_snapshot(courses, sections, meetings)

    assert {c.code for c in listed} == {"CAS AA 101", "CAS BB 200", "CAS FF 600"}
    aa = next(c for c in listed if c.code == "CAS AA 101")
    assert aa.credits == 4
    assert aa.hub_units == ["Critical Thinking", "Ethical Reasoning"]
    assert aa.prerequisites == ["CAS ZZ 100."]

    by_id = {s.id: s for s in secs}
    assert by_id["1001"].days == ["Mon", "Wed", "Fri"] and by_id["1001"].start == "09:05" and by_id["1001"].building_code == "CAS"
    assert by_id["1002"].component == "discussion" and by_id["1002"].building_code is None  # no room assigned yet
    assert "1003" not in by_id  # unscheduled discussion dropped
    assert by_id["1009"].component == "lecture"  # "Independent" kept as an ordinary class

    # a section with two meeting slots becomes two linked records; the main one has the most days
    main, extra = by_id["1004"], by_id["1004.2"]
    assert main.linked_to is None and main.days == ["Tue", "Thu"]
    assert extra.linked_to == "1004" and extra.days == ["Thu"] and extra.start == "18:30" and extra.component == "lecture"

    assert all(s.seats_open is None for s in secs)  # the catalog has no seat counts
    assert stats["courses_listed"] == 3
    assert stats["sections_listed"] == 4 and stats["meeting_records_listed"] == 5  # 1001, 1002, 1004, 1009 + the extra meeting
    assert stats["sections_weekend"] == 1 and stats["sections_self_overlap"] == 1
    assert stats["credits_zero_or_fractional"] == 1 and stats["missing_component"] == 1 and stats["no_class_sections"] == 1
