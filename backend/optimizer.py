"""CP-SAT schedule generator. Uses only CatalogSource models (Course, Section) plus a
building/dorm coordinate lookup passed in by the caller.

Hard: exactly one section per chosen course component (lecture, and lab/discussion if the
course has one), no time overlaps, credits in range. TBA/online sections never conflict
and have no travel. Full sections (seats_open == 0) are not offered.

Soft (weights configurable, minimised): tight transitions, dorm<->campus travel, walking
between classes, long gaps, classes outside the preferred window; rewarded: a >=30 min
free block overlapping 11:00-14:00 on each day.

Each day is modelled as an optional-node circuit (depot -> classes in time order -> depot),
so "consecutive classes" is exact and overlaps are impossible by construction.
"""
from __future__ import annotations

import math
from typing import Literal

from ortools.sat.python import cp_model
from pydantic import BaseModel

from clients.catalog import Course, Section
from locations import LocationInfo, walking_seconds

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
PACE = {"slow": 1.3, "normal": 1.0, "fast": 0.8}  # multiplies the 1.3 m/s base walking time
MEAL_LO, MEAL_HI, MEAL_MIN = 11 * 60, 14 * 60, 30
FALLBACK_WALK_MIN = 10  # used (and flagged) when a building has no known coordinates
SCALE = 10  # weights are floats; the solver works in integer tenths


class Weights(BaseModel):
    tight: float = 150           # per tight transition
    dorm_travel: float = 3       # per minute walking dorm->first / last->dorm
    between_travel: float = 1    # per minute walking between consecutive classes
    long_gap: float = 1          # per minute of a gap beyond long_gap_minutes
    time_pref: float = 1         # per minute a class falls outside earliest_start..latest_end
    meal: float = 100            # reward per day with a >=30 min free block in 11:00-14:00
    unknown_location: float = 20 # per meeting of a class with no usable location, so "no walk time" is not a free pass


class ScheduleRequest(BaseModel):
    required: list[str]
    optional: list[str] = []
    min_credits: int
    max_credits: int
    dorm_id: str | None = None
    earliest_start: str = "09:00"
    latest_end: str = "18:00"
    walking_pace: Literal["slow", "normal", "fast"] = "normal"
    buffer_minutes: int = 5
    long_gap_minutes: int = 90
    weights: Weights = Weights()
    top_n: int = 3
    min_diff: int = 2            # a new schedule must drop >=this many sections of each earlier one
    time_limit_s: float = 5.0


def hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def fmt(t: int) -> str:
    return f"{t // 60:02d}:{t % 60:02d}"


def timed(s: Section) -> bool:
    return bool(s.days and s.start and s.end)


class Ctx:
    """Request + coordinates -> walking times. Collects warnings instead of failing."""

    def __init__(self, req: ScheduleRequest, building_coords: dict[str, tuple[float, float]],
                 dorm_coord: tuple[float, float] | None, all_sections: list[Section]):
        self.req, self.coords, self.dorm = req, building_coords, dorm_coord
        self.days = WEEKDAYS + sorted({d for s in all_sections for d in s.days} - set(WEEKDAYS))
        self.pace = PACE[req.walking_pace]
        self.earliest, self.latest = hm(req.earliest_start), hm(req.latest_end)
        self.w = {k: round(v * SCALE) for k, v in req.weights.model_dump().items()}
        self.unknown: set[str] = set()  # building codes missing from the table (approximate fallback walk)
        self._cache: dict = {}
        self.info = LocationInfo(building_coords)
        self.dorm_approx = req.dorm_id not in self.info.verified_dorms

    def _min(self, p1, p2) -> int:
        return math.ceil(walking_seconds(*p1, *p2) * self.pace / 60)

    def walk(self, a: str | None, b: str | None) -> int:
        if a == b:
            return 0
        if a is None or b is None:
            return 0
        key = (a, b)
        if key not in self._cache:
            if a in self.coords and b in self.coords:
                self._cache[key] = self._min(self.coords[a], self.coords[b])
            else:
                self.unknown.update(c for c in (a, b) if c not in self.coords)
                self._cache[key] = FALLBACK_WALK_MIN
        return self._cache[key]

    def dorm_walk(self, b: str | None) -> int:
        if self.dorm is None or b is None:
            return 0
        if b not in self.coords:
            self.unknown.add(b)
            return FALLBACK_WALK_MIN
        return self._min(self.dorm, self.coords[b])

    def sec_status(self, s: Section) -> str:
        """ok | approximate | unknown (see locations.LocationInfo)."""
        return self.info.status(s.building_code, s.room)

    def leg(self, a: Section, b: Section) -> tuple[int | None, bool]:
        """(walk minutes, approximate). minutes is None when either class has no usable location."""
        sa, sb = self.sec_status(a), self.sec_status(b)
        if "unknown" in (sa, sb):
            return None, False
        if a.building_code == b.building_code:
            return 0, False
        return self.walk(a.building_code, b.building_code), sa != "ok" or sb != "ok"

    def dorm_leg(self, s: Section) -> tuple[int | None, bool]:
        st = self.sec_status(s)
        if st == "unknown":
            return None, False
        return self.dorm_walk(s.building_code), st != "ok" or self.dorm_approx

    def time_pen(self, s: Section) -> int:
        if not timed(s):
            return 0
        per_day = max(0, self.earliest - hm(s.start)) + max(0, hm(s.end) - self.latest)
        return per_day * len(s.days)


def _meal_ok(lo: int, hi: int) -> bool:
    return min(hi, MEAL_HI) - max(lo, MEAL_LO) >= MEAL_MIN


def score(sections: list[Section], ctx: Ctx) -> dict:
    """Exact metrics + weighted cost for a finished schedule (also used by baselines)."""
    req, w = ctx.req, ctx.w
    tight = between = dorm = gap_excess = meal_class_days = empty_days = 0
    longest_gap, class_days, transitions, meal_missing = 0, 0, [], []
    approx, unknown_trans = False, 0
    for d in ctx.days:
        todays = sorted((s for s in sections if timed(s) and d in s.days), key=lambda s: hm(s.start))
        if not todays:
            empty_days += 1
            continue
        class_days += 1
        for s in (todays[0], todays[-1]):
            m, ap = ctx.dorm_leg(s)
            if m is not None:
                dorm += m
                approx |= ap
        free = [(0, hm(todays[0].start)), (hm(todays[-1].end), 1440)]
        for a, b in zip(todays, todays[1:]):
            gap = hm(b.start) - hm(a.end)
            walk, ap = ctx.leg(a, b)
            # no usable location -> no walk time: not counted as tight and left out of travel totals
            is_tight = walk is not None and gap < walk + req.buffer_minutes
            if walk is None:
                unknown_trans += 1
            else:
                between += walk
                approx |= ap
            tight += is_tight
            gap_excess += max(0, gap - req.long_gap_minutes)
            longest_gap = max(longest_gap, gap)
            free.append((hm(a.end), hm(b.start)))
            transitions.append(dict(day=d, from_section=a.id, to_section=b.id, from_building=a.building_code,
                                    to_building=b.building_code, gap_minutes=gap, walk_minutes=walk, tight=is_tight,
                                    approximate=ap, location_unknown=walk is None,
                                    unknown_why=None if walk is not None else (
                                        ctx.info.unknown_reason(a.building_code, a.room) or ctx.info.unknown_reason(b.building_code, b.room))))
        if any(_meal_ok(lo, hi) for lo, hi in free):
            meal_class_days += 1
        else:
            meal_missing.append(d)
    time_pen = sum(ctx.time_pen(s) for s in sections)
    unknown_secs = [s for s in sections if timed(s) and ctx.sec_status(s) == "unknown"]
    unknown_meetings = sum(len(s.days) for s in unknown_secs)
    cost10 = (w["unknown_location"] * unknown_meetings + w["tight"] * tight + w["dorm_travel"] * dorm + w["between_travel"] * between
              + w["long_gap"] * gap_excess + w["time_pref"] * time_pen
              - w["meal"] * (meal_class_days + empty_days))
    travel = between + dorm
    return dict(
        tight_transitions=tight, travel_minutes=travel,
        travel_minutes_range=[round(travel * 0.8), round(travel * 1.3)],  # walking speed varies
        dorm_travel_minutes=dorm, between_class_travel_minutes=between,
        meal_window_days=meal_class_days, class_days=class_days, meal_missing_days=meal_missing,
        longest_gap_minutes=longest_gap, off_window_minutes=time_pen,
        credits=0, cost=cost10 / SCALE, _cost10=cost10, transitions=transitions,
        approximate=approx, unknown_transitions=unknown_trans, unknown_location_sections=[s.id for s in unknown_secs],
    )


def validate(sections: list[Section], courses: dict[str, Course], all_sections: list[Section], req: ScheduleRequest) -> str | None:
    """Return None if hard constraints hold, else a short reason (used to check every method)."""
    chosen = {s.course_code for s in sections}
    if not set(req.required) <= chosen:
        return "missing required course"
    cred = sum(courses[c].credits for c in chosen)
    if not req.min_credits <= cred <= req.max_credits:
        return f"credits {cred} out of range"
    need = {(s.course_code, s.component) for s in all_sections if s.course_code in chosen}
    got = [(s.course_code, s.component) for s in sections]
    if len(got) != len(set(got)) or set(got) != need:
        return "component coverage wrong"
    for d in WEEKDAYS:
        t = sorted((s for s in sections if timed(s) and d in s.days), key=lambda s: hm(s.start))
        if any(hm(a.end) > hm(b.start) for a, b in zip(t, t[1:])):
            return f"overlap on {d}"
    return None


def _diagnose(req, courses, by_course, candidates) -> str:
    missing = [c for c in req.required if c not in courses]
    if missing:
        return f"Required course(s) not in the catalog: {', '.join(missing)}."
    req_credits = sum(courses[c].credits for c in req.required)
    if req_credits > req.max_credits:
        return f"Required courses alone total {req_credits} credits, above your maximum of {req.max_credits}."
    for c in req.required:
        if not by_course.get(c):
            return f"{c} has no sections in the catalog."
        for comp in {s.component for s in by_course.get(c, [])}:
            if not candidates.get((c, comp)):
                return f"Every {comp} section of {c} is full, so it cannot be scheduled."
    if req_credits + sum(courses[c].credits for c in req.optional if c in courses) < req.min_credits:
        return f"Even with every optional course, credits stay under your minimum of {req.min_credits}."
    return "No combination of sections avoids time overlaps for these courses and credit limits. Try fewer required courses or more optional ones."


def generate(courses_list: list[Course], sections_list: list[Section], req: ScheduleRequest,
             building_coords: dict[str, tuple[float, float]], dorm_coord: tuple[float, float] | None) -> dict:
    ctx = Ctx(req, building_coords, dorm_coord, sections_list)
    courses = {c.code: c for c in courses_list}
    warnings: list[str] = []
    optional = [c for c in dict.fromkeys(req.optional) if c not in req.required]
    for c in optional:
        if c not in courses:
            warnings.append(f"Optional course {c} is not in the catalog and was ignored.")
    optional = [c for c in optional if c in courses]
    by_course: dict[str, list[Section]] = {}
    for s in sections_list:
        by_course.setdefault(s.course_code, []).append(s)
    candidates: dict[tuple[str, str], list[Section]] = {}
    for c in [*req.required, *optional]:
        for s in by_course.get(c, []):
            if s.seats_open != 0:  # full sections cannot be enrolled in
                candidates.setdefault((c, s.component), []).append(s)
    if dorm_coord is None:
        warnings.append("Dorm not found: dorm-to-class travel was left out of the scoring.")

    base = dict(label="Sample data (synthetic)", warnings=warnings)
    bad = _diagnose(req, courses, by_course, candidates)
    if any(c not in courses for c in req.required):
        return {**base, "status": "infeasible", "reason": bad, "schedules": []}

    found: list[dict] = []
    for _ in range(req.top_n):
        diff_try = [req.min_diff, 1] if req.min_diff > 1 else [1]
        sol = None
        for diff in diff_try:
            sol = _solve(courses, candidates, optional, req, ctx, [f["_ids"] for f in found], diff)
            if sol is not None:
                break
        if sol is None:
            break
        found.append(sol)

    if not found:
        return {**base, "status": "infeasible", "reason": bad, "schedules": []}
    out = []
    for rank, f in enumerate(found, 1):
        sched = _describe(rank, f, courses, req, ctx, found[0] if rank > 1 else None)
        out.append(sched)
    if ctx.unknown:
        warnings.append(f"Building(s) {', '.join(sorted(ctx.unknown))} are missing from the buildings table, so walks to or from them use an approximate {FALLBACK_WALK_MIN}-min estimate.")
    return {**base, "status": "ok", "schedules": out,
            "note": None if len(out) == req.top_n else f"Only {len(out)} distinct schedule(s) exist for this request."}


def _solve(courses, candidates, optional, req, ctx, previous: list[frozenset], min_diff: int) -> dict | None:
    m = cp_model.CpModel()
    w = ctx.w
    codes = [*req.required, *optional]
    chosen = {c: (m.NewConstant(1) if c in req.required else m.NewBoolVar(f"c_{c}")) for c in codes}
    x: dict[str, cp_model.IntVar] = {}
    for (c, comp), secs in candidates.items():
        for s in secs:
            x[s.id] = m.NewBoolVar(f"x_{s.id}")
        m.Add(sum(x[s.id] for s in secs) == chosen[c])
    for c in codes:  # a course whose required component has no open section cannot be chosen
        comps = {k for (cc, k) in candidates if cc == c}
        if not comps:
            m.Add(chosen[c] == 0)
    m.Add(sum(courses[c].credits * chosen[c] for c in codes) >= req.min_credits)
    m.Add(sum(courses[c].credits * chosen[c] for c in codes) <= req.max_credits)
    for ids in previous:
        m.Add(sum(x[i] for i in ids if i in x) <= len(ids) - min_diff)

    all_secs = {s.id: s for secs in candidates.values() for s in secs}
    terms: list[tuple[cp_model.IntVar, int]] = [
        (x[i], w["time_pref"] * ctx.time_pen(s) + (w["unknown_location"] * len(s.days) if timed(s) and ctx.sec_status(s) == "unknown" else 0))
        for i, s in all_secs.items()]
    const = 0
    for d in ctx.days:
        nodes = [s for s in all_secs.values() if timed(s) and d in s.days]
        if not nodes:
            const -= w["meal"]  # empty day always gets the meal reward (matches score())
            continue
        empty = m.NewBoolVar(f"empty_{d}")
        arcs = [(0, 0, empty)]
        qual = []
        for i, a in enumerate(nodes, 1):
            sa, ea = hm(a.start), hm(a.end)
            arcs.append((i, i, x[a.id].Not()))
            first, last = m.NewBoolVar(""), m.NewBoolVar("")
            arcs += [(0, i, first), (i, 0, last)]
            dm = ctx.dorm_leg(a)[0] or 0  # unknown location -> no dorm travel counted
            terms += [(first, w["dorm_travel"] * dm), (last, w["dorm_travel"] * dm)]
            if _meal_ok(0, sa):
                qual.append(first)
            if _meal_ok(ea, 1440):
                qual.append(last)
            for j, b in enumerate(nodes, 1):
                if i == j or ea > hm(b.start):
                    continue
                lit = m.NewBoolVar("")
                arcs.append((i, j, lit))
                gap, walk = hm(b.start) - ea, ctx.leg(a, b)[0]
                coef = (w["tight"] * (walk is not None and gap < walk + req.buffer_minutes) + w["between_travel"] * (walk or 0)
                        + w["long_gap"] * max(0, gap - req.long_gap_minutes))
                terms.append((lit, coef))
                if _meal_ok(ea, hm(b.start)):
                    qual.append(lit)
        m.AddCircuit(arcs)
        ok = m.NewBoolVar(f"meal_{d}")
        m.Add(ok <= sum(qual) + empty)
        terms.append((ok, -w["meal"]))
    m.Minimize(sum(v * c for v, c in terms if c) + const)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = req.time_limit_s
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = 1
    status = solver.Solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None
    ids = frozenset(i for i in x if solver.Value(x[i]))
    secs = sorted((all_secs[i] for i in ids), key=lambda s: (s.course_code, s.component))
    return dict(_ids=ids, sections=secs, objective10=round(solver.ObjectiveValue()),
                optimal=status == cp_model.OPTIMAL)


def _describe(rank, f, courses, req, ctx, best) -> dict:
    secs: list[Section] = f["sections"]
    met = score(secs, ctx)
    chosen = sorted({s.course_code for s in secs})
    met["credits"] = sum(courses[c].credits for c in chosen)
    met["objective_check"] = met["_cost10"] == f["objective10"]  # solver cost == recomputed cost
    flags = _flags(secs, met, req, ctx)
    explanation = _explain(rank, secs, met, req, ctx, best)
    met.pop("_cost10")
    return dict(
        rank=rank, optimal=f["optimal"], credits=met["credits"],
        courses=[dict(code=c, title=courses[c].title, credits=courses[c].credits, required=c in req.required) for c in chosen],
        sections=[s.model_dump() | {"location_status": ctx.sec_status(s) if timed(s) else "n/a",
                                      "location_reason": ctx.info.unknown_reason(s.building_code, s.room) if timed(s) else None} for s in secs],
        metrics=met, flags=flags, explanation=explanation,
    )


def _flags(secs, met, req, ctx):
    flags = []
    for t in met["transitions"]:
        if t["tight"]:
            flags.append(dict(kind="tight_transition", level="warn", why=(
                f"{t['day']}: {t['gap_minutes']} min between classes in {t['from_building']} and {t['to_building']}, "
                f"but the walk is about {t['walk_minutes']} min plus a {req.buffer_minutes}-min buffer. You may be late.")))
    for s in secs:
        if timed(s) and hm(s.start) < ctx.earliest:
            flags.append(dict(kind="early_class", level="warn", why=f"{s.course_code} {s.section_label} starts at {s.start}, before your preferred {req.earliest_start}."))
        if timed(s) and hm(s.end) > ctx.latest:
            flags.append(dict(kind="late_class", level="warn", why=f"{s.course_code} {s.section_label} ends at {s.end}, after your preferred {req.latest_end}."))
        if s.seats_open is not None and 0 < s.seats_open <= 5:
            flags.append(dict(kind="low_seats", level="info", why=f"{s.course_code} {s.section_label} shows only {s.seats_open} open seat(s) in the sample data; it may fill before you register."))
        if not timed(s):
            flags.append(dict(kind="tba_online", level="info", why=f"{s.course_code} {s.section_label} is TBA/online, so it is assumed to cause no conflicts or travel."))
    for s in secs:
        why = ctx.info.unknown_reason(s.building_code, s.room) if timed(s) else None
        if why:
            flags.append(dict(kind="location_unknown", level="warn", why=(
                f"{s.course_code} {s.section_label}: location unknown ({why}). It has no walking time and is left out of transition-risk checks.")))
    if met["approximate"]:
        flags.append(dict(kind="approximate_walk", level="info", why=(
            "Some walking times are approximate: a building is missing from the buildings table or its coordinates are unverified.")))
    for d in met["meal_missing_days"]:
        flags.append(dict(kind="no_meal_window", level="warn", why=f"{d}: no free block of 30+ minutes between 11:00 and 14:00, so lunch may be rushed."))
    if met["longest_gap_minutes"] > req.long_gap_minutes:
        flags.append(dict(kind="long_gap", level="info", why=f"Longest wait between two classes is {met['longest_gap_minutes']} min."))
    return flags


def _explain(rank, secs, met, req, ctx, best) -> str:
    days = [d for d in WEEKDAYS if any(timed(s) and d in s.days for s in secs)]
    starts = [hm(s.start) for s in secs if timed(s)]
    ends = [hm(s.end) for s in secs if timed(s)]
    p = []
    if starts:
        p.append(f"Classes run on {', '.join(days)}, between {fmt(min(starts))} and {fmt(max(ends))}.")
    t = met["tight_transitions"]
    p.append("No back-to-back transition is tighter than the estimated walk plus your buffer." if t == 0
             else f"{t} transition(s) are tight (less time than the estimated walk plus {req.buffer_minutes} min).")
    lo, hi = met["travel_minutes_range"]
    p.append(f"Estimated walking is about {lo}-{hi} min per week in total ({met['dorm_travel_minutes']} min nominal to and from your dorm).")
    p.append(f"A 30+ min free block during 11:00-14:00 exists on {met['meal_window_days']} of {met['class_days']} class days.")
    if met["unknown_location_sections"]:
        p.append(f"{len(met['unknown_location_sections'])} class(es) have an unknown location (no building, \"No Room\", or medical campus), so they are left out of walking and transition-risk checks.")
    if met["approximate"]:
        p.append("Some walking times are approximate (building missing from the table or unverified).")
    if met["off_window_minutes"]:
        p.append(f"{met['off_window_minutes']} class-minutes per week fall outside your {req.earliest_start}-{req.latest_end} window.")
    if best is not None:
        p.append(f"Ranked #{rank}: penalty score {met['cost']:g} vs {best['objective10'] / SCALE:g} for #1 (lower is better); it differs from #1 in different section choices, so it is a real alternative.")
    elif rank == 1:
        p.append("Best overall under your weights.")
    p.append("Walking times are estimates (straight-line distance x 1.3 at a typical pace) from approximate building locations.")
    return " ".join(p)
