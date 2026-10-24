"""Weekly recurring iCalendar export: classes (with a leave-by alarm) + optional meal windows.

The alarm uses the WALKING leave-by (bus times are live-only and cannot be put in a recurring
event). Meal windows are between-class gaps that fit 30 min plus the walk to the nearest dining
hall; dining hours are not checked because the API only publishes today's.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, datetime, timedelta, timezone

from leaveby import SIGMA, TZ, Z90, _walk_min
from locations import LocationInfo, dining_coords
from optimizer import hm

BYDAY = {"Mon": "MO", "Tue": "TU", "Wed": "WE", "Thu": "TH", "Fri": "FR", "Sat": "SA", "Sun": "SU"}
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
LABEL = {"lecture": "Lecture", "lab": "Lab", "discussion": "Discussion"}
CAL_NAME = "Compass schedule (sample data, synthetic)"
VTIMEZONE = """BEGIN:VTIMEZONE
TZID:America/New_York
BEGIN:DAYLIGHT
TZOFFSETFROM:-0500
TZOFFSETTO:-0400
TZNAME:EDT
DTSTART:19700308T020000
RRULE:FREQ=YEARLY;BYMONTH=3;BYDAY=2SU
END:DAYLIGHT
BEGIN:STANDARD
TZOFFSETFROM:-0400
TZOFFSETTO:-0500
TZNAME:EST
DTSTART:19701101T020000
RRULE:FREQ=YEARLY;BYMONTH=11;BYDAY=1SU
END:STANDARD
END:VTIMEZONE""".split("\n")


def esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line: str) -> list[str]:
    """RFC 5545: lines over 75 octets are folded with CRLF + space (never splitting a UTF-8 char)."""
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode()) > (75 if not out else 74):
            out.append(cur)
            cur = ch
        else:
            cur += ch
    out.append(cur)
    return [out[0]] + [" " + x for x in out[1:]]


def _dt(d: date, minutes: int) -> str:
    return f"{d.strftime('%Y%m%d')}T{minutes // 60:02d}{minutes % 60:02d}00"


def _next(day: str, today: date) -> date:
    return today + timedelta(days=(DAYS.index(day) - today.weekday()) % 7)


def build(entry: dict, buildings: dict, dorms: dict, include_meals: bool, weeks: int, now: datetime | None = None) -> str:
    now = now or datetime.now(TZ)
    today = now.date()
    secs = [s for s in entry["schedule"]["sections"] if s["days"] and s["start"] and s["end"]]
    pace = entry.get("walking_pace", "normal")
    dorm = dorms.get(entry.get("dorm_id"))
    halls = dining_coords()
    info = LocationInfo(buildings)
    stamp = now.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    L = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Compass//Schedule export//EN", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
         f"X-WR-CALNAME:{esc(CAL_NAME)}", "X-WR-TIMEZONE:America/New_York", *VTIMEZONE]

    def event(uid_key, summary, d, start, end, desc, location=None, rrule_day=None, transparent=False, alarm=None):
        uid = hashlib.sha1(uid_key.encode()).hexdigest()[:20] + "@compass.local"
        ev = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{stamp}", f"DTSTART;TZID=America/New_York:{_dt(d, start)}",
              f"DTEND;TZID=America/New_York:{_dt(d, end)}", f"RRULE:FREQ=WEEKLY;COUNT={weeks};BYDAY={BYDAY[rrule_day]}",
              f"SUMMARY:{esc(summary)}", f"DESCRIPTION:{esc(desc)}"]
        if location:
            ev.append(f"LOCATION:{esc(location)}")
        if transparent:
            ev += ["TRANSP:TRANSPARENT", "CATEGORIES:Meal window"]
        if alarm:
            ev += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{esc(alarm[1])}", f"TRIGGER:-PT{alarm[0]}M", "END:VALARM"]
        ev.append("END:VEVENT")
        L.extend(x for line in ev for x in fold(line))

    for day in DAYS:
        todays = sorted((s for s in secs if day in s["days"]), key=lambda s: hm(s["start"]))
        d0 = _next(day, today)
        for i, s in enumerate(todays):
            prev = todays[i - 1] if i else None
            o_pt = buildings.get(prev["building_code"]) if prev else dorm
            d_pt = buildings.get(s["building_code"])
            why_unknown = info.unknown_reason(s["building_code"], s.get("room")) or (info.unknown_reason(prev["building_code"], prev.get("room")) if prev else None)
            if why_unknown:
                lead, basis = None, f"location unknown ({why_unknown})"  # no walking time, so no leave-by alarm
            elif o_pt and d_pt:
                w = _walk_min(o_pt, d_pt, pace)
                lead, basis = math.ceil(max(w, 1) * math.exp(SIGMA * Z90)), f"~{w:.0f} min walk from {'your previous class' if prev else 'your dorm'}"
                if info.status(s["building_code"], s.get("room")) != "ok" or not prev:
                    basis += ", approximate"
            else:
                lead, basis = 10, "approximate: a location is missing from the buildings table, 10 min assumed"
            title = f"{s['course_code']} {LABEL.get(s['component'], '')} {s['section_label']}".replace("  ", " ")
            loc = " ".join(x for x in (s["building_code"], s["room"]) if x)
            event(f"class|{s['id']}|{day}", title, d0, hm(s["start"]), hm(s["end"]),
                  ("Sample (synthetic) course from Compass. " + (f"Leave-by alarm is {lead} min before class ({basis}, ~90% on-time walking estimate)." if lead else f"No leave-by alarm: {basis}.")),
                  loc or None, day, alarm=(lead, f"Leave now for {s['course_code']} ({basis})") if lead else None)
        if include_meals:
            for a, b in zip(todays, todays[1:]):
                pa, pb = buildings.get(a["building_code"]), buildings.get(b["building_code"])
                if not (pa and pb and halls):
                    continue
                if info.unknown_reason(a["building_code"], a.get("room")) or info.unknown_reason(b["building_code"], b.get("room")):
                    continue  # no walking time to a dining hall
                gap = hm(b["start"]) - hm(a["end"])
                name, best = min(((n, _walk_min(pa, c, pace) + _walk_min(c, pb, pace)) for n, c in halls.items()), key=lambda x: x[1])
                if gap >= 30 + math.ceil(best):
                    event(f"meal|{a['id']}|{b['id']}|{day}", "Meal window (optional)", d0, hm(a["end"]), hm(b["start"]),
                          f"{gap}-minute gap fits a 30-minute meal plus about {best:.0f} min of walking to the closest dining hall ({name}). "
                          "Dining hours are not checked for this day.", None, day, transparent=True)
    L.append("END:VCALENDAR")
    return "\r\n".join(L) + "\r\n"
