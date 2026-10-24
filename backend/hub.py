"""Hub gap-filler: sections that cover Hub units you still need and fit the current schedule.

A suggestion is a whole course (its lecture plus any lab/discussion) that
  - overlaps nothing in the schedule,
  - creates no tight transition (none involving a new section, none more overall),
  - keeps a lunch window on every day that already had one,
  - stays within max_credits if given.
Hub unit names come straight from the catalog's hub_units values.
"""
from __future__ import annotations

from itertools import product

from baselines import _clash
from clients.catalog import Course, Section
from optimizer import Ctx, ScheduleRequest, score, timed

MAX_COMBOS = 40


def all_units(courses: list[Course]) -> list[str]:
    return sorted({u for c in courses for u in c.hub_units})


def suggestions(entry: dict, completed: list[str], courses: list[Course], sections: list[Section],
                coords: dict, dorm_coord, max_credits: int | None, limit: int) -> dict:
    sched = [Section(**s) for s in entry["schedule"]["sections"]]
    cmap = {c.code: c for c in courses}
    in_sched = {s.course_code for s in sched}
    units = all_units(courses)
    done = {u for u in completed if u in units}
    covered_now = {u for code in in_sched if code in cmap for u in cmap[code].hub_units}
    remaining = [u for u in units if u not in done and u not in covered_now]
    req = ScheduleRequest(required=[], min_credits=0, max_credits=99, dorm_id=entry.get("dorm_id"), walking_pace=entry.get("walking_pace", "normal"))
    ctx = Ctx(req, coords, dorm_coord, sections)
    base = score(sched, ctx)
    base_credits = sum(cmap[c].credits for c in in_sched if c in cmap)
    by_course: dict[str, list[Section]] = {}
    extras: dict[str, list[Section]] = {}
    for s in sections:
        by_course.setdefault(s.course_code, []).append(s)
        if s.linked_to:
            extras.setdefault(s.linked_to, []).append(s)

    rejected = {"credits": 0, "no_open_section": 0, "overlap": 0, "tight_transition": 0, "lunch_window": 0}
    out = []
    for c in courses:
        gain = [u for u in c.hub_units if u in remaining]
        if c.code in in_sched or not gain:
            continue
        if max_credits is not None and base_credits + c.credits > max_credits:
            rejected["credits"] += 1
            continue
        comps: dict[str, list[Section]] = {}
        for s in by_course.get(c.code, []):
            if s.linked_to is None and s.seats_open != 0:
                comps.setdefault(s.component, []).append(s)
        if not comps or len(comps) < len({s.component for s in by_course.get(c.code, []) if s.linked_to is None}):
            rejected["no_open_section"] += 1
            continue
        best, why_not = None, set()
        for bundle in list(product(*comps.values()))[:MAX_COMBOS]:
            new = [r for s in bundle for r in [s, *extras.get(s.id, [])]]  # extra meetings come along
            if any(_clash(a, b) for i, a in enumerate(new) for b in [*sched, *new[i + 1:]]):
                why_not.add("overlap")
                continue
            m = score([*sched, *new], ctx)
            ids = {s.id for s in new}
            if m["tight_transitions"] > base["tight_transitions"] or any(t["tight"] and (t["from_section"] in ids or t["to_section"] in ids) for t in m["transitions"]):
                why_not.add("tight_transition")
                continue
            if not set(m["meal_missing_days"]) <= set(base["meal_missing_days"]):
                why_not.add("lunch_window")
                continue
            added = m["travel_minutes"] - base["travel_minutes"]
            if best is None or added < best[0]:
                best = (added, new, m)
        if best is None:
            for r in why_not or {"no_open_section"}:
                rejected[r] += 1
            continue
        added, new, m = best
        extra_day = m["class_days"] > base["class_days"]
        why = [f"Covers {', '.join(gain)}.", "No time overlaps and no tight transitions.",
               f"Keeps a lunch window on every day that already had one ({m['meal_window_days']} of {m['class_days']} class days).",
               f"Adds about {max(added, 0)} min of walking per week (estimate)."]
        unk = [s for s in new if timed(s) and ctx.sec_status(s) == "unknown"]
        if unk:
            why.append("Location unknown for " + ", ".join(f"{lbl} ({r})" for lbl, r in {s.section_label: ctx.info.unknown_reason(s.building_code, s.room) for s in unk}.items())
                        + ": walking and tight transitions could not be checked for it.")
        off = sum(ctx.time_pen(s) for s in new)
        if off:
            why.append(f"Note: meets outside a typical {req.earliest_start}-{req.latest_end} day ({off} class-minutes per week).")
        if extra_day:
            why.append("Adds a new class day.")
        if c.prerequisites:
            why.append(f"Prerequisites: {', '.join(c.prerequisites)}. Confirm you have met them.")
        low = [s for s in new if s.linked_to is None and s.seats_open is not None and s.seats_open <= 5]
        if low:
            why.append("Few open seats: " + ", ".join(f"{s.section_label} ({s.seats_open})" for s in low) + ".")
        out.append({
            "course": {"code": c.code, "title": c.title, "credits": c.credits, "hub_units": c.hub_units, "prerequisites": c.prerequisites},
            "covers": gain,
            "sections": [s.model_dump() | {"location_status": ctx.sec_status(s) if timed(s) else "n/a",
                                           "location_reason": ctx.info.unknown_reason(s.building_code, s.room) if timed(s) else None} for s in new],
            "after": {"tight_transitions": m["tight_transitions"], "meal_window_days": m["meal_window_days"], "class_days": m["class_days"],
                      "added_travel_minutes": max(added, 0), "credits": base_credits + c.credits},
            "why": " ".join(why), "_off": off, "location_unknown": bool(unk),
        })
    out.sort(key=lambda s: (-len(s["covers"]), s["location_unknown"], s["_off"] > 0, s["after"]["added_travel_minutes"], s["course"]["credits"]))
    for s in out:
        s.pop("_off")
    return {
        "hub_units": units, "completed": sorted(done), "covered_by_schedule": sorted(covered_now & set(units) - done),
        "remaining": remaining, "current": {"tight_transitions": base["tight_transitions"], "meal_window_days": base["meal_window_days"],
                                           "class_days": base["class_days"], "credits": base_credits},
        "suggestions": out[:limit], "total_found": len(out), "rejected_courses": rejected,
    }
