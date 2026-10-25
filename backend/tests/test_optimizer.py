"""Schedule optimizer: hard constraints, linked meetings, unknown locations and solver/score agreement."""
from clients.catalog import Course, SampleCatalogSource, Section
from locations import load_locations
from optimizer import ScheduleRequest, generate, validate

COORDS = {"CDS": (42.3503, -71.1033), "SCI": (42.3503, -71.1002)}


def course(code, credits=4):
    return Course(code=code, title=f"Title {code}", credits=credits, hub_units=[], prerequisites=[])


def sec(sid, code, days, start, end, building="CDS", component="lecture", linked_to=None):
    return Section(id=sid, course_code=code, section_label=sid, days=days, start=start, end=end, building_code=building,
                   room="1" if building else None, seats_open=None, component=component, linked_to=linked_to)


def request(required, optional=(), lo=4, hi=20, **kw):
    return ScheduleRequest(required=list(required), optional=list(optional), min_credits=lo, max_credits=hi, top_n=3, **kw)


def test_sample_catalog_schedules_satisfy_every_hard_constraint():
    catalog = SampleCatalogSource()
    buildings, _, _ = load_locations()
    coords = {code: (lat, lon) for code, _, lat, lon in buildings}
    req = request(["MA 101", "CS 111", "PH 101"], ["EC 101", "WR 100", "HI 150"], lo=14, hi=18)
    result = generate(catalog.courses(), catalog.sections(), req, coords, None)

    assert result["status"] == "ok"
    assert len(result["schedules"]) >= 2
    by_code = {c.code: c for c in catalog.courses()}
    seen = set()
    for schedule in result["schedules"]:
        chosen = [Section(**s) for s in schedule["sections"]]
        assert validate(chosen, by_code, catalog.sections(), req) is None  # credits, components, no overlaps
        assert schedule["metrics"]["objective_check"] is True  # the solver's cost equals an independent recomputation
        seen.add(frozenset(s.id for s in chosen))
    assert len(seen) == len(result["schedules"])  # the schedules are distinct


def test_extra_meetings_travel_with_their_section_and_cause_conflicts():
    courses = [course("AAA 100"), course("BBB 100")]
    sections = [
        sec("a1", "AAA 100", ["Mon"], "09:00", "09:50"),
        sec("a1.2", "AAA 100", ["Thu"], "18:30", "19:20", linked_to="a1"),  # evening session of the same section
        sec("b1", "BBB 100", ["Thu"], "18:30", "19:20"),
    ]
    clash = generate(courses, sections, request(["AAA 100", "BBB 100"]), COORDS, None)
    assert clash["status"] == "infeasible"  # b1 collides with a1's Thursday evening meeting

    sections.append(sec("b2", "BBB 100", ["Fri"], "10:00", "10:50"))
    ok = generate(courses, sections, request(["AAA 100", "BBB 100"]), COORDS, None)
    assert ok["status"] == "ok"
    ids = {s["id"] for s in ok["schedules"][0]["sections"]}
    assert ids == {"a1", "a1.2", "b2"}  # the extra meeting is always included, and b2 is the only fit


def test_classes_without_a_known_location_are_not_counted_as_tight_or_travel():
    courses = [course("AAA 100"), course("BBB 100")]
    sections = [sec("a1", "AAA 100", ["Mon"], "09:00", "09:50", building="CDS"),
                sec("b1", "BBB 100", ["Mon"], "10:00", "10:50", building=None)]  # 10-minute gap, but no location
    metrics = generate(courses, sections, request(["AAA 100", "BBB 100"]), COORDS, None)["schedules"][0]["metrics"]
    assert metrics["tight_transitions"] == 0
    assert metrics["unknown_transitions"] == 1
    assert metrics["between_class_travel_minutes"] == 0
    assert metrics["transitions"][0]["location_unknown"] is True and metrics["transitions"][0]["walk_minutes"] is None


def test_a_tight_walk_between_known_locations_is_counted():
    courses = [course("AAA 100"), course("BBB 100")]
    sections = [sec("a1", "AAA 100", ["Mon"], "09:00", "09:50", building="CDS"),
                sec("b1", "BBB 100", ["Mon"], "09:55", "10:45", building="SCI")]  # ~3-minute walk is more than the 5-minute gap minus buffer
    metrics = generate(courses, sections, request(["AAA 100", "BBB 100"], buffer_minutes=5), COORDS, None)["schedules"][0]["metrics"]
    assert metrics["tight_transitions"] == 1


def test_infeasible_requests_explain_why():
    courses = [course("AAA 100"), course("BBB 100")]
    sections = [sec("a1", "AAA 100", ["Mon"], "09:00", "09:50"), sec("b1", "BBB 100", ["Tue"], "09:00", "09:50")]
    unknown = generate(courses, sections, request(["AAA 100", "NOPE 999"]), COORDS, None)
    assert unknown["status"] == "infeasible" and "not in the catalog" in unknown["reason"]
    too_many = generate(courses, sections, request(["AAA 100", "BBB 100"], lo=2, hi=6), COORDS, None)
    assert too_many["status"] == "infeasible" and "credit" in too_many["reason"].lower()
