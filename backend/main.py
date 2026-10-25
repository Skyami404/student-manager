import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

import assignments
import db
from clients import dining, transit
from clients.catalog import get_catalog_source
import delay_model
import ics
import social
import hub
import meals
import leaveby
import transit_logger
from locations import load_locations
from transit_net import get_watch, network, set_watch, watched
from optimizer import ScheduleRequest, generate

catalog = get_catalog_source()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.seed(catalog, load_locations())
    sched = transit_logger.start()
    yield
    if sched:
        sched.shutdown(wait=False)


app = FastAPI(title="Compass API", lifespan=lifespan)
app.include_router(social.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if o.strip()],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _row(o):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/courses")
def courses(q: str = "", limit: int = 100, s: Session = Depends(db.get_session)):
    """Search by code or title. Codes match with or without spaces ("CASMA123" finds "CAS MA 123").
    limit <= 0 returns everything (used by onboarding to validate codes and list Hub areas)."""
    stmt = select(db.Course).order_by(db.Course.code)
    q = q.strip()
    if q:
        esc = lambda x: x.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        no_space = esc(q.upper().replace(" ", ""))
        stmt = stmt.where(or_(func.replace(func.upper(db.Course.code), " ", "").like(f"%{no_space}%", escape="\\"),
                              db.Course.title.ilike(f"%{esc(q)}%", escape="\\")))
    if limit > 0:
        stmt = stmt.limit(min(limit, 5000))
    return [_row(c) for c in s.scalars(stmt)]


@app.get("/sections")
def sections(course_id: str, s: Session = Depends(db.get_session)):
    stmt = select(db.Section).where(db.Section.course_code == course_id).order_by(db.Section.section_label)
    return [_row(x) for x in s.scalars(stmt)]


@app.get("/buildings")
def buildings(s: Session = Depends(db.get_session)):
    return [_row(b) for b in s.scalars(select(db.Building).order_by(db.Building.code))]


@app.get("/dorms")
def dorms(s: Session = Depends(db.get_session)):
    return [_row(d) for d in s.scalars(select(db.Dorm).order_by(db.Dorm.name))]


_status_cache: tuple[float, dict] = (0.0, {})


def _location_quality() -> dict:
    """How trustworthy walking times are: unverified or missing buildings make them approximate."""
    from locations import LocationInfo
    with db.SessionLocal() as s:
        coords = {b.code: (b.lat, b.lon) for b in s.scalars(select(db.Building))}
    info = LocationInfo(coords)
    return {"buildings_in_table": len(coords), "buildings_verified": len(info.verified & set(coords)),
            "approximate": len(info.verified & set(coords)) < len(coords),
            "medical_or_no_room_codes": sorted(info.medical | info.no_room)}


@app.get("/data-status")
def data_status():
    """Per-source status: live | cached | sample | unavailable. Probed at most once a minute."""
    global _status_cache
    ts, cached = _status_cache
    if cached and time.time() - ts < 60:
        return cached
    _, t = transit.routes()
    _, d = dining.locations()
    locs = load_locations()[2]
    result = {
        "catalog": {"status": catalog.status, "synthetic": catalog.synthetic, "label": catalog.label, "as_of": catalog.as_of,
                    "term": getattr(catalog, "term_label", None)},
        "transit": {"status": t},
        "dining": {"status": d},
        "locations": {"status": "sample", "source": locs, "synthetic": locs != "csv", **_location_quality()},
        "delay_model": delay_model.status() | {"logger": transit_logger.STATE | {"rows": transit_logger.total_rows()}},
    }
    _status_cache = (time.time(), result)
    return result


@app.post("/schedules/generate")
def schedules_generate(req: ScheduleRequest, s: Session = Depends(db.get_session)):
    """Top schedules from the CP-SAT optimizer, built only from the CatalogSource models."""
    if req.min_credits > req.max_credits:
        raise HTTPException(422, "min_credits must not exceed max_credits")
    coords = {b.code: (b.lat, b.lon) for b in s.scalars(select(db.Building))}
    dorm = s.get(db.Dorm, req.dorm_id) if req.dorm_id else None
    res = generate(catalog.courses(), catalog.sections(), req, coords, (dorm.lat, dorm.lon) if dorm else None)
    res["synthetic_catalog"], res["label"] = catalog.synthetic, catalog.label
    for sch in res["schedules"]:
        leaveby.add_transition_risk(sch["metrics"]["transitions"])
        sch["id"] = leaveby.save_schedule(sch, req.dorm_id, req.walking_pace)
    return res


class WatchBody(BaseModel):
    dorm_id: str | None = None
    building_codes: list[str] = []


def _coords(s: Session):
    return ({d.code: (d.lat, d.lon) for d in s.scalars(select(db.Dorm))},
            {b.code: (b.lat, b.lon) for b in s.scalars(select(db.Building))})


@app.post("/watch")
def watch(body: WatchBody, s: Session = Depends(db.get_session)):
    """Tell the transit logger which dorm/buildings matter (stops near them get logged)."""
    set_watch(body.dorm_id, body.building_codes)
    net, (dorms, blds) = network(), _coords(s)
    w = watched(net, dorms, blds) if net else {"physical_stops": [], "routes": []}
    return {"physical_stops": w["physical_stops"], "routes": w["routes"]}


def _model():
    net = network()
    pairs = []
    if net:
        with db.SessionLocal() as s:
            d, b = _coords(s)
        pairs = [(r["route_id"], r["physical_id"]) for r in watched(net, d, b)["route_stops"]]
    return delay_model.get_model(pairs)


@app.get("/leave-by")
def leave_by(schedule_id: str, class_id: str, day: str | None = None, now: str | None = None, s: Session = Depends(db.get_session)):
    entry = leaveby.load_schedule(schedule_id)
    if entry is None:
        raise HTTPException(404, "Unknown schedule_id (generate schedules first).")
    tz = ZoneInfo("America/New_York")
    when = datetime.fromisoformat(now).astimezone(tz) if now else datetime.now(tz)
    dorms, blds = _coords(s)
    try:
        return leaveby.leave_by(entry, class_id, day, when, blds, dorms, network(), _model)
    except KeyError:
        raise HTTPException(404, "class_id is not in that schedule")
    except ValueError as e:
        raise HTTPException(422, str(e))


@app.get("/alerts")
def alerts(routes: str | None = None, s: Session = Depends(db.get_session)):
    """Service alerts for the user's shuttle routes (or ?routes=1,4). Empty list if none."""
    net = network()
    if routes:
        ids = [r for r in routes.split(",") if r]
    else:
        d, b = _coords(s)
        ids = watched(net, d, b)["routes"] if net else []
    return leaveby.alerts_for(ids, net)


@app.get("/meals")
def meals_endpoint(day: str | None = None, schedule_id: str | None = None, diet: str = "", meal_minutes: int = 30,
                   s: Session = Depends(db.get_session)):
    """Schedule gaps that fit a meal (>= meal_minutes + walking) at dining halls open then.
    diet: comma list of vegetarian,vegan,gluten_free,halal. schedule_id optional (halls/hours only without it)."""
    if day is None:
        day = meals.DAYS[datetime.now(ZoneInfo("America/New_York")).weekday()]
    if day not in meals.DAYS:
        raise HTTPException(422, "day must be one of " + ", ".join(meals.DAYS))
    entry = None
    if schedule_id:
        entry = leaveby.load_schedule(schedule_id)
        if entry is None:
            raise HTTPException(404, "Unknown schedule_id (generate schedules first).")
    dorms, blds = _coords(s)
    return meals.find_meals(entry, day, [d for d in diet.split(",") if d], max(10, min(meal_minutes, 120)), blds, dorms)


@app.get("/assignments")
def assignments_due(days: int = 14):
    """Assignments due soon from the Blackboard / Gradescope calendar links in backend/.env (sample list if none set)."""
    return assignments.upcoming(max(1, min(days, 60)))


@app.get("/hub/suggestions")
def hub_suggestions(schedule_id: str, completed: list[str] = Query(default=[]), max_credits: int | None = None,
                    limit: int = 8, s: Session = Depends(db.get_session)):
    """Courses covering Hub units you still need that fit the schedule without tight transitions
    or losing a lunch window. completed: repeat the param for each finished Hub unit."""
    entry = leaveby.load_schedule(schedule_id)
    if entry is None:
        raise HTTPException(404, "Unknown schedule_id (generate schedules first).")
    dorms, blds = _coords(s)
    res = hub.suggestions(entry, completed, catalog.courses(), catalog.sections(), blds, dorms.get(entry.get("dorm_id")), max_credits, max(1, min(limit, 30)))
    res["synthetic_catalog"], res["label"] = catalog.synthetic, catalog.label
    return res


@app.get("/export.ics")
def export_ics(schedule_id: str, meals: bool = True, weeks: int = 15, s: Session = Depends(db.get_session)):
    """Weekly recurring class events (with a leave-by alarm) and optional meal-window events."""
    entry = leaveby.load_schedule(schedule_id)
    if entry is None:
        raise HTTPException(404, "Unknown schedule_id (generate schedules first).")
    dorms, blds = _coords(s)
    body = ics.build(entry, blds, dorms, meals, max(1, min(weeks, 40)), synthetic=catalog.synthetic)
    return Response(body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="compass-schedule.ics"'})
