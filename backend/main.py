import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

import db
from clients import dining, transit
from clients.catalog import get_catalog_source
from locations import load_locations
from optimizer import ScheduleRequest, generate

catalog = get_catalog_source()


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    db.seed(catalog, load_locations())
    yield


app = FastAPI(title="Compass API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


def _row(o):
    return {c.name: getattr(o, c.name) for c in o.__table__.columns}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/courses")
def courses(q: str = "", s: Session = Depends(db.get_session)):
    stmt = select(db.Course).order_by(db.Course.code)
    q = q.strip()
    if q:
        like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        stmt = stmt.where(or_(db.Course.code.ilike(like, escape="\\"), db.Course.title.ilike(like, escape="\\")))
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
        "catalog": {"status": "sample" if catalog.synthetic else "live", "synthetic": catalog.synthetic, "label": catalog.label},
        "transit": {"status": t},
        "dining": {"status": d},
        "locations": {"status": "sample", "source": locs, "synthetic": locs != "csv"},
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
    res["synthetic_catalog"] = catalog.synthetic
    return res
