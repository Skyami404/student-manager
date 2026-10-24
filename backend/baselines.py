"""Baselines for comparison with the optimizer. Both return a list of Section or None."""
import random

from clients.catalog import Course, Section
from optimizer import ScheduleRequest, hm, timed

ORDER = {"lecture": 0, "lab": 1, "discussion": 2}


def _clash(a: Section, b: Section) -> bool:
    if not (timed(a) and timed(b)) or not set(a.days) & set(b.days):
        return False
    return hm(a.start) < hm(b.end) and hm(b.start) < hm(a.end)


def _components(code: str, sections: list[Section]) -> list[list[Section]]:
    """Open (non-full) sections of a course grouped by component, lecture first."""
    open_ = [s for s in sections if s.course_code == code and s.seats_open != 0 and s.linked_to is None]
    allc = {s.component for s in sections if s.course_code == code and s.linked_to is None}
    return [[s for s in open_ if s.component == k] for k in sorted(allc, key=ORDER.get)]


def _with_extras(s: Section, sections: list[Section]) -> list[Section]:
    return [s] + [x for x in sections if x.linked_to == s.id]


def _place(code, sections, chosen, pick) -> list[Section] | None:
    added = []
    for group in _components(code, sections):
        ok = [s for s in group if not any(_clash(r, o) for r in _with_extras(s, sections) for o in chosen + added)]
        if not ok:
            return None
        added += _with_extras(pick(ok), sections)
    return added


def random_valid(courses: dict[str, Course], sections: list[Section], req: ScheduleRequest, rng: random.Random,
                 attempts: int = 500) -> list[Section] | None:
    for _ in range(attempts):
        codes, credits = list(req.required), sum(courses[c].credits for c in req.required)
        opts = [c for c in req.optional if c in courses and c not in codes]
        rng.shuffle(opts)
        for c in opts:
            if credits >= req.min_credits and rng.random() < 0.5:
                break
            if credits + courses[c].credits <= req.max_credits:
                codes.append(c)
                credits += courses[c].credits
        if not req.min_credits <= credits <= req.max_credits:
            continue
        rng.shuffle(codes)
        chosen: list[Section] = []
        for c in codes:
            got = _place(c, sections, chosen, rng.choice)
            if got is None:
                break
            chosen += got
        else:
            return chosen
    return None


def greedy_first_fit(courses: dict[str, Course], sections: list[Section], req: ScheduleRequest) -> list[Section] | None:
    """Take courses in the given order and the first open section that fits. No backtracking."""
    chosen: list[Section] = []
    credits = 0
    for c in req.required:
        got = _place(c, sections, chosen, lambda ok: ok[0])
        if got is None:
            return None
        chosen += got
        credits += courses[c].credits
    for c in req.optional:
        if credits >= req.min_credits:
            break
        if c in courses and c not in req.required and credits + courses[c].credits <= req.max_credits:
            got = _place(c, sections, chosen, lambda ok: ok[0])
            if got is not None:
                chosen += got
                credits += courses[c].credits
    return chosen if req.min_credits <= credits <= req.max_credits else None
