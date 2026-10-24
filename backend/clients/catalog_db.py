"""BU course catalog from the private READ-ONLY database (schema `catalog`: courses, sections, meetings, terms,
dataset_info; columns as listed in fixtures/catalog_schema.json).

SELECT only. The session is also opened read-only (server side + SQLAlchemy), so a write cannot happen even by
mistake. Credentials come from the DB_* environment variables and are never printed or logged.

What is listed (everything else in the catalog is left out on purpose):
  - one term (default Spring 2027 = 2271), undergraduate career (UGRD), regular full-term session ("1")
  - Charles River campus sections with a weekday meeting time (unscheduled sections cannot be placed)
  - class-like section types only (lecture, discussion, lab and their variants); independent/directed study,
    applied music, clinical-style placeholders etc. are dropped
  - sections that meet Mon-Fri (a weekend meeting, more than 3 distinct meeting slots, or slots that overlap each
    other drop the section). A section with several time/place slots becomes one record per slot, linked together
  - whole-number, non-zero credits (the optimizer works in whole credits)
  - a course is listed only if every component it has (lecture/lab/discussion) still has a placeable section
Hub areas and prerequisites exist only as free text in the course description; they are parsed from it.
Seat counts are not in the database, so seats_open is always None (unknown).
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

from clients.catalog import Course, Section

load_dotenv(Path(__file__).resolve().parent.parent / ".env")  # DB_* (does not override variables already set)

DEFAULT_TERM = "2271"
CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"

# BU "section_type" -> our component. Note: in this catalog "Independent" is just the generic type of ordinary
# classes (e.g. "Introduction to Neuroscience"), NOT independent study; real independent study has no meeting time.
COMPONENT = {
    "Lecture": "lecture", "Independent": "lecture", "Class and Performance": "lecture", "Music Organization": "lecture",
    "Other": "lecture", "Didactic": "lecture", "Large Group": "lecture",
    "Discussion": "discussion", "Small Group": "discussion",
    "Laboratory": "lab", "Pre-laboratory": "lab",
}
DAY = {"M": "Mon", "T": "Tue", "W": "Wed", "R": "Thu", "F": "Fri"}  # S/U (weekend) are dropped

# ---------------------------------------------------------------------------------------------------------------
# Hub areas. The description says e.g. "Effective Fall 2018, this course fulfills a single unit in each of the
# following BU Hub areas: A, B, C." Names are matched against this vocabulary (taken from the catalog itself,
# including its typos and variants) instead of splitting on commas, because one real area contains commas.
# ---------------------------------------------------------------------------------------------------------------
_ROMAN = {"i": "I", "1": "I", "ii": "II", "2": "II"}
_HUB_PATTERNS: list[tuple[str, str]] = [
    (r"philosophical\s+inquiry\s+and\s+life'?s\s+meanings?", "Philosophical Inquiry and Life's Meanings"),
    (r"aesthetic\s+exploration", "Aesthetic Exploration"),
    (r"historical\s+consciousness", "Historical Consciousness"),
    (r"global\s+citizenship(?:\s+(?:and|&)\s+intercultural\s+literacy)?", "Global Citizenship and Intercultural Literacy"),
    (r"(?:the\s+)?individual\s+in\s+community", "The Individual in Community"),
    (r"scientific\s+inquiry\s+(?:ii|2)\b", "Scientific Inquiry II"),
    (r"scientific\s+inquiry\s+(?:i|1)\b", "Scientific Inquiry I"),
    (r"social\s+inquiry\s+(?:ii|2)\b", "Social Inquiry II"),
    (r"social\s+inquiry\s+(?:i|1)\b", "Social Inquiry I"),
    (r"quantitative\s+reasoning\s+(?:ii|2)\b", "Quantitative Reasoning II"),
    (r"quantitative\s+reasoning\s+(?:i|1)\b", "Quantitative Reasoning I"),
    (r"ethical\s+reasoning", "Ethical Reasoning"),
    (r"critical\s+thinking", "Critical Thinking"),
    (r"research\s+and\s+information\s+literacy", "Research and Information Literacy"),
    (r"teamwork\s*(?:/|and)\s*collaboration", "Teamwork/Collaboration"),
    (r"creativity\s*/\s*innovation", "Creativity/Innovation"),
    (r"oral\s+(?:and/or|and)\s+signed\s+communication", "Oral and/or Signed Communication"),
    (r"digital\s*/?\s*(?:multi)?medi(?:a|al)\s+expression", "Digital/Multimedia Expression"),
    (r"writing[-\s]*intensive(?:\s+course)?", "Writing-Intensive Course"),
    (r"first[-\s]*year\s+writing\s+seminar", "First-Year Writing Seminar"),
    (r"writing\s*[,:]?\s*research\s*,?\s*(?:and|&)\s*inquiry|research\s*(?:and|&)\s*inquiry", "Writing, Research, and Inquiry"),
]
_HUB_RE = re.compile("|".join(f"(?P<g{i}>{p})" for i, (p, _) in enumerate(_HUB_PATTERNS)), re.I)
# The marker that introduces the list of areas: "following BU Hub areas:", "follow Hub area:" (no colon in a few),
# or "... the BU Hub area of X"
_HUB_MARK = re.compile(r"(?:(?:following|follow)\s+(?:BU\s+)?Hub\s+areas?\s*:?|BU\s+Hub\s+areas?\s+of)\s*", re.I)
_EFFECTIVE = re.compile(r"Effective\s+(Fall|Spring|Summer)\s+(\d{4})", re.I)


def parse_hub_units(description: str | None) -> list[str]:
    """Hub areas the course fulfills, from its description text. [] when the text names none.
    If the description lists areas in several sentences (the course changed over time), the sentence with the
    latest "Effective <term> <year>" wins; with no dates the last one wins."""
    d = description or ""
    found: list[tuple[tuple[int, int], int, list[str]]] = []
    for i, m in enumerate(_HUB_MARK.finditer(d)):
        seg = d[m.end(): m.end() + 400]
        end = re.search(r"\.(?:\s|$)", seg)  # the list ends at the sentence's period
        seg = seg[: end.start()] if end else seg
        units: list[str] = []
        for hit in _HUB_RE.finditer(seg):
            name = _HUB_PATTERNS[int(hit.lastgroup[1:])][1]
            if name not in units:
                units.append(name)
        # "Effective Fall 2020" is in the text just before the marker
        before = list(_EFFECTIVE.finditer(d[max(0, m.start() - 160): m.start()]))
        when = (int(before[-1].group(2)), {"spring": 1, "summer": 2, "fall": 3}[before[-1].group(1).lower()]) if before else (0, 0)
        if units:
            found.append((when, i, units))
    return max(found)[2] if found else []


_PREREQ = re.compile(r"^\s*(?:Undergraduate\s+)?Prerequisites?\s*:\s*(.+?)(?:\s+-\s+|\s*$)", re.S | re.I)


def parse_prerequisites(description: str | None) -> list[str]:
    """The prerequisite sentence at the start of the description, as ONE unparsed text item (it is free text such
    as "CAS PY 105 or equivalent"), or [] when there is none. Not checked against what a student has taken."""
    m = _PREREQ.match(description or "")
    if not m:
        return []
    text = re.sub(r"\s+", " ", m.group(1)).strip()
    text = text if len(text) <= 240 else text[:237].rstrip() + "..."
    return [] if not text or text.lower().rstrip(".") in {"none", "n/a"} else [text]


def format_code(subject: str, display_code: str) -> str:
    """CASPH251 -> "CAS PH 251"; the college is the first 3 letters of the subject. Keeps suffixes (CASCH204P)."""
    if len(subject) == 5 and display_code.upper().startswith(subject.upper()):
        return f"{subject[:3]} {subject[3:]} {display_code[len(subject):]}".upper()
    return display_code


def hhmm(t: str) -> str | None:
    m = re.match(r"^(\d{1,2})[.:](\d{2})", (t or "").strip())
    return f"{int(m.group(1)):02d}:{m.group(2)}" if m else None


def _slots_overlap(slot_list) -> bool:
    for i, ((s1, e1, *_), d1) in enumerate(slot_list):
        for (s2, e2, *_), d2 in slot_list[i + 1:]:
            if d1 & d2 and s1 < e2 and s2 < e1:
                return True
    return False


def build_snapshot(course_rows, section_rows, meeting_rows) -> tuple[list[Course], list[Section], dict]:
    """Pure function: raw catalog rows (dict-like) -> our models + a stats dict describing what was left out."""
    stats = defaultdict(int)
    slots: dict[str, dict] = defaultdict(lambda: defaultdict(set))  # section_key -> (start,end,bld,room) -> {days}
    for m in meeting_rows:
        day, st, en = (m["day"] or "").strip(), hhmm(m["start_time"]), hhmm(m["end_time"])
        if day and st and en:
            slots[m["section_key"]][(st, en, (m["building_code"] or "").strip(), (m["room"] or "").strip())] |= set(day)
    by_course: dict[str, list[dict]] = defaultdict(list)
    for s in section_rows:
        by_course[s["course_key"]].append(s)

    courses: list[Course] = []
    sections: list[Section] = []
    seen_ids: set[str] = set()
    for c in course_rows:
        stats["courses_considered"] += 1
        classlike = [s for s in by_course.get(c["course_key"], []) if s["section_type"] in COMPONENT]
        if not classlike:
            stats["no_class_sections"] += 1
            continue
        kept: list[tuple[dict, Section]] = []
        for s in classlike:
            g = slots.get(s["section_key"])
            if not g:
                stats["sections_unscheduled"] += 1
                continue
            slot_list = sorted(g.items(), key=lambda kv: (-len(kv[1]), kv[0][0]))  # main slot = most days, then earliest
            if any(not days <= set(DAY) for _, days in slot_list):  # Saturday / Sunday
                stats["sections_weekend"] += 1
                continue
            if len(slot_list) > 3:
                stats["sections_too_many_slots"] += 1
                continue
            if _slots_overlap(slot_list):
                stats["sections_self_overlap"] += 1
                continue
            sid = str(s["class_number"])
            if sid in seen_ids:
                stats["sections_duplicate_id"] += 1
                continue
            seen_ids.add(sid)
            for k, ((st, en, bld, room), days) in enumerate(slot_list):
                kept.append((s, Section(
                    id=sid if k == 0 else f"{sid}.{k + 1}", course_code="", section_label=s["section"] or sid,
                    days=[DAY[d] for d in "MTWRF" if d in days], start=st, end=en,
                    building_code=bld or None, room=room or None, seats_open=None, component=COMPONENT[s["section_type"]],
                    linked_to=None if k == 0 else sid)))
            if len(slot_list) > 1:
                stats["sections_with_several_meetings"] += 1
        if not kept:
            stats["no_placeable_sections"] += 1
            continue
        # every component the course has must still have a placeable section, or the schedule would silently omit it
        if {COMPONENT[s["section_type"]] for s in classlike} != {x.component for _, x in kept}:
            stats["missing_component"] += 1
            continue
        primary = [s for s, x in kept if x.component == "lecture" and x.linked_to is None] or [s for s, x in kept if x.linked_to is None]
        credit_values = {float(s["credits"]) for s in primary if s["credits"] not in (None, "")}
        if len(credit_values) != 1:
            stats["credits_ambiguous"] += 1
            continue
        credit = credit_values.pop()
        if credit <= 0 or credit != int(credit):
            stats["credits_zero_or_fractional"] += 1
            continue
        code = format_code(c["subject"], c["display_code"])
        courses.append(Course(code=code, title=(c["title"] or code).strip(), credits=int(credit),
                              hub_units=parse_hub_units(c["description"]), prerequisites=parse_prerequisites(c["description"])))
        for _, x in kept:
            x.course_code = code
            sections.append(x)
    codes = [c.code for c in courses]
    assert len(codes) == len(set(codes)), "duplicate course codes"
    stats["courses_listed"], stats["sections_listed"] = len(courses), sum(1 for x in sections if x.linked_to is None)
    stats["meeting_records_listed"] = len(sections)
    return courses, sections, dict(stats)


# ------------------------------------------------------------------------------ live read-only database
def _engine():
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    host = os.environ.get("DB_HOST", "")
    if not host:
        raise RuntimeError("DB_HOST not set")
    if (os.environ.get("DB_ENGINE") or "postgres").lower() != "postgres":
        raise RuntimeError("only a PostgreSQL catalog database is supported")
    url = URL.create("postgresql+psycopg2", username=os.environ.get("DB_USER") or None, password=os.environ.get("DB_PASSWORD") or None,
                     host=host, port=int(os.environ.get("DB_PORT") or 5432), database=os.environ.get("DB_NAME") or "postgres")
    args = {"connect_timeout": 5, "options": "-c default_transaction_read_only=on -c statement_timeout=30000"}
    if os.environ.get("DB_SSL", "1") == "1":
        args["sslmode"] = "require"
    return create_engine(url, connect_args=args)


_WHERE = ("c.term_code = :term AND c.academic_career = 'UGRD' AND c.session_code = '1'")
SQL_COURSES = f"SELECT c.course_key, c.display_code, c.subject, c.title, c.description FROM catalog.courses c WHERE {_WHERE}"
SQL_SECTIONS = ("SELECT s.section_key, s.course_key, s.class_number, s.section, s.credits, s.section_type "
                f"FROM catalog.sections s JOIN catalog.courses c ON c.course_key = s.course_key WHERE {_WHERE} AND s.campus = 'Charles River'")
SQL_MEETINGS = ("SELECT m.section_key, m.day, m.start_time, m.end_time, m.building_code, m.room "
                "FROM catalog.meetings m JOIN catalog.sections s ON s.section_key = m.section_key "
                f"JOIN catalog.courses c ON c.course_key = s.course_key WHERE {_WHERE} AND s.campus = 'Charles River'")
SQL_TERM = "SELECT description FROM catalog.terms WHERE term_code = :term AND academic_career = 'UGRD' LIMIT 1"
SQL_INFO = "SELECT refreshed_at FROM catalog.dataset_info LIMIT 1"


def fetch_live(term: str) -> dict:
    """Run the SELECTs and return a snapshot dict (see build_snapshot). Raises on any failure."""
    from sqlalchemy import text
    eng = _engine()
    try:
        with eng.connect().execution_options(postgresql_readonly=True) as conn:
            p = {"term": term}
            courses = [dict(r) for r in conn.execute(text(SQL_COURSES), p).mappings()]
            sections = [dict(r) for r in conn.execute(text(SQL_SECTIONS), p).mappings()]
            meetings = [dict(r) for r in conn.execute(text(SQL_MEETINGS), p).mappings()]
            t = conn.execute(text(SQL_TERM), p).first()
            info = conn.execute(text(SQL_INFO)).first()
    finally:
        eng.dispose()
    cs, ss, stats = build_snapshot(courses, sections, meetings)
    return {"term": term, "term_label": (t[0] if t else term), "as_of": (info[0].date().isoformat() if info and info[0] else None),
            "fetched_at": time.time(), "stats": stats,
            "courses": [c.model_dump() for c in cs], "sections": [s.model_dump() for s in ss]}


def _cache_path(term: str) -> Path:
    return CACHE_DIR / f"catalog_{term}.json"


def save_cache(snap: dict) -> None:
    CACHE_DIR.mkdir(exist_ok=True)
    _cache_path(snap["term"]).write_text(json.dumps(snap))


def load_cache(term: str) -> dict | None:
    try:
        snap = json.loads(_cache_path(term).read_text())
        return snap if snap.get("courses") else None
    except (OSError, ValueError):
        return None


def load_snapshot(term: str | None = None) -> tuple[dict, str] | None:
    """(snapshot, "live" | "cached") or None when neither the database nor a disk cache is available."""
    term = term or os.environ.get("CATALOG_TERM") or DEFAULT_TERM
    try:
        snap = fetch_live(term)
        if snap["courses"]:
            save_cache(snap)
            return snap, "live"
    except Exception as e:  # never print the message: it can contain the host or user name
        print(f"catalog: live database unavailable ({type(e).__name__}); trying the disk cache")
    snap = load_cache(term)
    return (snap, "cached") if snap else None
