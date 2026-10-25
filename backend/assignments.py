"""Assignments due, read from calendar (iCal / .ics) feed links. No logins, no API keys.

- Blackboard: Calendar > Settings > Share calendar gives a private .ics link -> BLACKBOARD_ICS_URL.
- Gradescope has no feed of its own. Any .ics link works for GRADESCOPE_ICS_URL (for example a
  Google Calendar "secret address in iCal format" that a Gradescope-to-calendar tool fills).
  Otherwise students add Gradescope items by hand on the Briefing page (stored in the browser).

Links are secrets (anyone with one can read the calendar): they live in backend/.env only and are
never returned or logged. Fallback order per feed: live -> disk cache (backend/.cache) -> skipped.
With no feed set at all, a small clearly-labelled sample list is returned so the demo has content.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import requests

from clients.bu_http import CACHE_DIR  # also loads backend/.env

TZ = ZoneInfo("America/New_York")
FEEDS = {"Blackboard": "BLACKBOARD_ICS_URL", "Gradescope": "GRADESCOPE_ICS_URL"}


def _unfold(text: str) -> list[str]:
    """RFC 5545: a line starting with a space or tab continues the previous one."""
    out: list[str] = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if line[:1] in (" ", "\t") and out:
            out[-1] += line[1:]
        elif line:
            out.append(line)
    return out


def _unesc(v: str) -> str:
    return re.sub(r"\\([\\;,nN])", lambda m: "\n" if m.group(1) in "nN" else m.group(1), v)


def _when(params: str, value: str) -> tuple[datetime, bool] | None:
    """Parse DTSTART/DUE. Returns (aware datetime, all_day)."""
    value = value.strip()
    try:
        if "VALUE=DATE" in params.upper() and "VALUE=DATE-TIME" not in params.upper() or re.fullmatch(r"\d{8}", value):
            d = datetime.strptime(value[:8], "%Y%m%d")
            return d.replace(hour=23, minute=59, tzinfo=TZ), True
        dt = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    except ValueError:
        return None
    if value.endswith("Z"):
        return dt.replace(tzinfo=timezone.utc), False
    m = re.search(r"TZID=([^;:]+)", params)
    try:
        tz = ZoneInfo(m.group(1).strip('"')) if m else TZ
    except Exception:  # unknown / Windows-style TZID: assume Boston time
        tz = TZ
    return dt.replace(tzinfo=tz), False


def parse_ics(text: str, source: str) -> list[dict]:
    items, ev = [], None
    for line in _unfold(text):
        name, _, value = line.partition(":")
        key, _, params = name.partition(";")
        key = key.upper()
        if key == "BEGIN" and value.upper() in ("VEVENT", "VTODO"):
            ev = {}
        elif key == "END" and value.upper() in ("VEVENT", "VTODO") and ev is not None:
            due = ev.get("DUE") or ev.get("DTEND") if value.upper() == "VTODO" else ev.get("DTSTART")
            if due and ev.get("SUMMARY"):
                when = _when(*due)
                if when:
                    items.append({
                        "id": f"{source}:{ev.get('UID', ev['SUMMARY'])[1]}:{when[0].isoformat()}",
                        "title": _unesc(ev["SUMMARY"][1]).strip(),
                        "course": _unesc(ev.get("CATEGORIES", ev.get("LOCATION", ("", "")))[1]).strip() or None,
                        "due": when[0].astimezone(TZ).isoformat(),
                        "all_day": when[1],
                        "url": ev.get("URL", (None, None))[1],
                        "source": source,
                    })
            ev = None
        elif ev is not None and key in ("SUMMARY", "DTSTART", "DTEND", "DUE", "UID", "URL", "CATEGORIES", "LOCATION"):
            ev[key] = (params, value)
    return items


def _fetch(source: str, url: str) -> tuple[list[dict] | None, str]:
    cache = CACHE_DIR / f"assignments_{source.lower()}.json"
    try:
        r = requests.get(url.replace("webcal://", "https://", 1), timeout=8, headers={"User-Agent": "Compass/1.0"})
        r.raise_for_status()
        if "BEGIN:VCALENDAR" not in r.text[:2000]:
            raise ValueError("not an iCal feed")
        items = parse_ics(r.text, source)
        CACHE_DIR.mkdir(exist_ok=True)
        cache.write_text(json.dumps(items))
        return items, "live"
    except (requests.RequestException, ValueError):
        pass  # never log the URL: it is a private link
    if cache.exists():
        try:
            return json.loads(cache.read_text()), "cached"
        except ValueError:
            pass
    return None, "unavailable"


def _sample(now: datetime) -> list[dict]:
    def at(days: int, h: int) -> str:
        m = 59 if h == 23 else 0
        return (now + timedelta(days=days)).replace(hour=h, minute=m, second=0, microsecond=0).isoformat()
    rows = [("Problem Set 4", "CS 111", 1, 23, "Gradescope"), ("Lab report: Kinematics", "PY 211", 2, 17, "Blackboard"),
            ("Reading response 6", "WR 120", 3, 12, "Blackboard"), ("Midterm review quiz", "MA 123", 5, 23, "Gradescope")]
    return [{"id": f"sample:{i}", "title": t, "course": c, "due": at(d, h), "all_day": False, "url": None, "source": s}
            for i, (t, c, d, h, s) in enumerate(rows)]


def upcoming(days: int = 14, now: datetime | None = None) -> dict:
    now = now or datetime.now(TZ)
    feeds, items = {}, []
    for source, env in FEEDS.items():
        url = os.environ.get(env, "").strip()
        if not url:
            feeds[source] = "not_set"
            continue
        got, status = _fetch(source, url)
        feeds[source] = status
        items += got or []
    sample = all(s == "not_set" for s in feeds.values())
    if sample:
        items = _sample(now)
    lo, hi = now - timedelta(days=1), now + timedelta(days=days)
    seen, out = set(), []
    for it in sorted(items, key=lambda x: x["due"]):
        if lo <= datetime.fromisoformat(it["due"]) <= hi and it["id"] not in seen:
            seen.add(it["id"])
            out.append(it)
    return {"assignments": out, "feeds": feeds, "sample": sample, "days": days}
