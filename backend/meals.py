"""Find schedule gaps that fit a meal (>= meal_minutes + walking) at an open dining hall.

Dining data: hours and menus are published for TODAY only (the gateway ignores ?date=). For other
weekdays we reuse the hours last observed on that weekday (labelled) and cannot know the menu.
Dietary fields available per item: vegetarian, vegan, gluten_free, halal. There is no allergen field.
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from clients import dining
from clients.bu_http import CACHE_DIR
from locations import LocationInfo, dining_coords, walking_seconds
from optimizer import PACE, fmt, hm, timed

TZ = ZoneInfo("America/New_York")
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
DIETS = {"vegetarian": "Vegetarian", "vegan": "Vegan", "gluten_free": "Gluten-free", "halal": "Halal"}  # fields that exist
DISCLAIMER = "Dietary info may be outdated; confirm with dining staff."
FALLBACK_WALK_MIN = 10
BEFORE_FIRST_MIN, AFTER_LAST_MIN = 120, 180  # how far outside the class day a meal is considered
HOURS_STORE = CACHE_DIR / "dining_hours.json"
_memo: dict = {"t": 0.0, "data": None}


def _load_today() -> dict:
    """{'date', 'weekday', 'status', 'halls': {id: {info, status_text, open_now, schedules, meals}}, 'allergy_notice'}"""
    if _memo["data"] and time.time() - _memo["t"] < 60:
        return _memo["data"]
    locs, status = dining.locations()
    out = {"status": status, "halls": {}, "date": None, "allergy_notice": None}
    for loc in (locs or {}).get("locations", []):
        m, s = dining.menu(loc["id"])
        if not m:
            continue
        out["date"] = out["date"] or m.get("date")
        out["status"] = s if s != "live" else out["status"]
        out["halls"][loc["id"]] = {"info": loc, "status_text": m.get("status"), "open_now": m.get("open_now"),
                                   "schedules": m.get("schedules", []), "meals": m.get("meals", []), "stale": m.get("stale", False)}
    if out["date"]:
        out["weekday"] = DAYS[datetime.fromisoformat(out["date"]).weekday()]
        if out["status"] == "live":
            _remember_hours(out)
    _memo.update(t=time.time(), data=out)
    return out


def _remember_hours(today: dict) -> None:
    try:
        store = json.loads(HOURS_STORE.read_text())
    except (OSError, ValueError):
        store = {}
    store[today["weekday"]] = {"date": today["date"], "halls": {h: v["schedules"] for h, v in today["halls"].items()}}
    CACHE_DIR.mkdir(exist_ok=True)
    HOURS_STORE.write_text(json.dumps(store))


def _hours_for(day: str, today: dict) -> tuple[dict, str | None, str]:
    """({hall_id: schedules}, observed_date, source) where source is today | last_observed | unavailable."""
    if today.get("weekday") == day:
        return {h: v["schedules"] for h, v in today["halls"].items()}, today["date"], "today"
    try:
        rec = json.loads(HOURS_STORE.read_text()).get(day)
    except (OSError, ValueError):
        rec = None
    if rec:
        return rec["halls"], rec["date"], "last_observed"
    return {}, None, "unavailable"


def _match(items: list[dict], diet: list[str]) -> list[dict]:
    return [i for i in items if all(i.get(f) for f in diet)]


def _meal_summary(meal: dict | None, diet: list[str]) -> dict:
    if not meal:
        return {"total_items": None, "matching_items": None, "examples": []}
    items = {i["id"]: i for st in meal["stations"] for i in st["items"]}.values()
    hit = _match(list(items), diet)
    names = list(dict.fromkeys(i["name"] for i in hit))
    return {"total_items": len(items), "matching_items": len(hit), "examples": names[:4]}


def _walk(a, b, pace: str, notes: set, label: str) -> int:
    if a is None or b is None:
        notes.add(f"No coordinates for {label}; a {FALLBACK_WALK_MIN}-min walk was assumed.")
        return FALLBACK_WALK_MIN
    return math.ceil(walking_seconds(*a, *b) * PACE[pace] / 60)


def find_meals(entry: dict | None, day: str, diet: list[str], meal_minutes: int, buildings: dict, dorms: dict) -> dict:
    diet = [d for d in diet if d in DIETS]
    today = _load_today()
    hours, hours_date, hours_source = _hours_for(day, today)
    is_today = hours_source == "today"
    coords = dining_coords()
    notes: set[str] = set()
    pace = (entry or {}).get("walking_pace", "normal")

    halls = []
    for hid, h in today["halls"].items():
        meals = []
        by_name = {m["name"]: m for m in h["meals"]}
        for sch in hours.get(hid, []):
            meals.append({**sch, **(_meal_summary(by_name.get(sch["meal"]), diet) if is_today else _meal_summary(None, diet))})
        halls.append({"id": hid, "name": h["info"]["name"], "short_name": h["info"]["short_name"], "campus": h["info"]["campus"],
                      "address": h["info"]["address"], "open_now": h["open_now"] if is_today else None,
                      "status_text": h["status_text"] if is_today else None, "meals": meals, "coords_known": hid in coords})
    if hours_source == "last_observed":
        notes.add(f"Dining hours for {day} are not published yet; showing hours last seen on {hours_date}. Menus are only available for today, so dietary matches are unknown.")
    elif hours_source == "unavailable":
        notes.add(f"Dining hours for {day} are not published (the dining API only covers today) and none were seen before. Check bu.edu/dining.")
    if today["status"] != "live":
        notes.add(f"Dining data is {today['status']}, not live; hours may be out of date.")
    if diet and not is_today:
        notes.add("Dietary filtering needs a published menu, which exists for today only.")

    gaps = []
    if entry:
        secs = [s for s in entry["schedule"]["sections"] if timed_dict(s) and day in s["days"]]
        secs.sort(key=lambda s: hm(s["start"]))
        gaps = _gaps(secs, day, entry, halls, hours, coords, buildings, dorms, diet, is_today, today, meal_minutes, pace, notes, LocationInfo(buildings))
    return {
        "day": day, "hours_source": hours_source, "hours_date": hours_date, "data_status": today["status"],
        "diet": diet, "diet_filters_available": [{"id": k, "label": v} for k, v in DIETS.items()],
        "allergen_filter": {"available": False, "reason": "The dining data has no structured allergen field, so allergens cannot be filtered reliably. Confirm with dining staff."},
        "disclaimer": DISCLAIMER,
        "allergy_notice": "Menus and ingredients can change. If you have a food allergy, speak with BU Dining staff before ordering.",
        "halls": halls, "gaps": gaps, "meal_minutes": meal_minutes, "notes": sorted(notes),
    }


def timed_dict(s: dict) -> bool:
    return bool(s["days"] and s["start"] and s["end"])


def _gaps(secs, day, entry, halls, hours, coords, buildings, dorms, diet, is_today, today, M, pace, notes, info):
    dorm = dorms.get(entry.get("dorm_id"))
    windows = []
    if secs:
        first, last = secs[0], secs[-1]
        windows.append(("before_first", hm(first["start"]) - BEFORE_FIRST_MIN, hm(first["start"]), ("dorm", entry.get("dorm_id"), dorm, None), ("class", first["building_code"], buildings.get(first["building_code"]), first)))
        for a, b in zip(secs, secs[1:]):
            windows.append(("between", hm(a["end"]), hm(b["start"]), ("class", a["building_code"], buildings.get(a["building_code"]), a), ("class", b["building_code"], buildings.get(b["building_code"]), b)))
        windows.append(("after_last", hm(last["end"]), min(hm(last["end"]) + AFTER_LAST_MIN, 23 * 60), ("class", last["building_code"], buildings.get(last["building_code"]), last), None))
    out = []
    for kind, gs, ge, origin, dest in windows:
        gs = max(gs, 0)
        if ge - gs < M:
            continue
        # a class with no usable location (no building, "No Room", medical campus) has no walking time
        why_unknown = None
        for end in (origin, dest):
            if end and end[3] is not None:
                r = info.unknown_reason(end[3]["building_code"], end[3].get("room"))
                if r:
                    why_unknown = f"{end[3]['course_code']}: {r}"
                    break
        if why_unknown:
            out.append({"kind": kind, "start": fmt(gs), "end": fmt(ge), "minutes": ge - gs, "from": origin[1], "to": dest[1] if dest else None,
                        "fits": None, "location_unknown": True, "options": [],
                        "why": f"Location unknown ({why_unknown}). Walking time to a dining hall can't be estimated, so whether a meal fits is unknown."})
            continue
        options = []
        for h in halls:
            wt = _walk(origin[2], coords.get(h["id"]), pace, notes, f"{origin[1]} or dining hall {h['short_name']}")
            wf = _walk(coords.get(h["id"]), dest[2], pace, notes, f"{dest[1]} or dining hall {h['short_name']}") if dest else 0
            for m in h["meals"]:
                lo, hi = max(gs + wt, hm(m["opens_at"])), min(ge - wf - M, hm(m["closes_at"]) - M)
                if lo > hi:
                    continue
                options.append({"hall_id": h["id"], "hall": h["short_name"], "meal": m["meal"], "walk_to_min": wt, "walk_from_min": wf,
                                "start_between": [fmt(lo), fmt(hi)], "matching_items": m["matching_items"], "total_items": m["total_items"],
                                "examples": m["examples"], "open_now": h["open_now"]})
        options.sort(key=lambda o: (-(o["matching_items"] or 0) if diet and is_today else 0, o["walk_to_min"] + o["walk_from_min"]))
        raw = ge - gs
        if options:
            why = f"{raw}-minute window. Each option leaves {M} min to eat plus the walking time shown, and the hall is open then."
        else:
            why = (f"{raw}-minute window, but no dining hall fits a {M}-minute meal plus walking while open. "
                   + ("Hours for this day are unknown." if not hours else "The halls are closed or too far away in that window."))
        if kind == "before_first":
            why = "Before your first class (from your dorm). " + why
        elif kind == "after_last":
            why = "After your last class. " + why
        out.append({"kind": kind, "start": fmt(max(gs, 0)), "end": fmt(ge), "minutes": raw, "from": origin[1], "to": dest[1] if dest else None,
                    "fits": bool(options), "location_unknown": False, "options": options, "why": why})
    return out
