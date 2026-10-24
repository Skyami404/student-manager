"""SQLAlchemy + SQLite models. Local app DB only; nothing is ever written to external DBs."""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import ForeignKey, create_engine, delete
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker
from sqlalchemy.types import JSON

DB_PATH = Path(__file__).resolve().parent / "compass.db"
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(engine, expire_on_commit=False)


def now():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Course(Base):
    __tablename__ = "courses"
    code: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    credits: Mapped[int]
    hub_units: Mapped[list] = mapped_column(JSON, default=list)
    prerequisites: Mapped[list] = mapped_column(JSON, default=list)


class Section(Base):
    __tablename__ = "sections"
    id: Mapped[str] = mapped_column(primary_key=True)
    course_code: Mapped[str] = mapped_column(ForeignKey("courses.code"), index=True)
    section_label: Mapped[str]
    days: Mapped[list] = mapped_column(JSON, default=list)
    start: Mapped[str | None]
    end: Mapped[str | None]
    building_code: Mapped[str | None]  # matches buildings.code (not enforced: real data may differ)
    room: Mapped[str | None]
    seats_open: Mapped[int | None]
    component: Mapped[str] = mapped_column(default="lecture")


class Building(Base):
    __tablename__ = "buildings"
    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    lat: Mapped[float]
    lon: Mapped[float]
    source: Mapped[str] = mapped_column(default="synthetic-seed")  # or "csv"; coords unverified


class Dorm(Base):
    __tablename__ = "dorms"
    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    lat: Mapped[float]
    lon: Mapped[float]
    source: Mapped[str] = mapped_column(default="synthetic-seed")


class User(Base):
    # Minimal personal data on purpose: no grades, no course names shared with friends.
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    display_name: Mapped[str | None]
    dorm_code: Mapped[str | None] = mapped_column(ForeignKey("dorms.code"))
    created_at: Mapped[datetime] = mapped_column(default=now)


class Friendship(Base):
    # Friends only ever see free time windows derived from schedules, never course names.
    __tablename__ = "friendships"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    friend_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[str] = mapped_column(default="pending")  # pending|accepted
    created_at: Mapped[datetime] = mapped_column(default=now)


class TransitLog(Base):
    # One row per observation of an upcoming bus arrival that has BOTH a live prediction
    # (estimate_at) and a posted time (scheduled_at). Datetimes are naive UTC.
    __tablename__ = "transit_log"
    id: Mapped[int] = mapped_column(primary_key=True)
    observed_at: Mapped[datetime] = mapped_column(default=now, index=True)
    endpoint: Mapped[str]
    stop_id: Mapped[str | None] = mapped_column(index=True)   # physical stop id
    route_id: Mapped[str | None] = mapped_column(index=True)
    route_stop_id: Mapped[str | None]                          # id used by the arrivals endpoint
    vehicle_id: Mapped[str | None]
    scheduled_at: Mapped[datetime | None] = mapped_column(index=True)
    predicted_at: Mapped[datetime | None]
    lead_seconds: Mapped[int | None]                           # predicted_at - observed_at (gateway 'seconds' is time to SCHEDULED, kept in payload)
    delay_seconds: Mapped[int | None]                          # predicted_at - scheduled_at (negative = early)
    is_live: Mapped[bool] = mapped_column(default=False)
    payload: Mapped[str | None]                                # raw arrival JSON


def init_db():
    from sqlalchemy import inspect
    insp = inspect(engine)
    # transit_log changed shape; it only ever held nothing useful before, so rebuild it.
    if insp.has_table("transit_log") and "scheduled_at" not in {c["name"] for c in insp.get_columns("transit_log")}:
        TransitLog.__table__.drop(engine)
    Base.metadata.create_all(engine)


def seed(catalog, locations):
    """Reload catalog + lookup tables from their sources (idempotent)."""
    buildings, dorms, loc_source = locations
    with SessionLocal() as s, s.begin():
        for model in (Section, Course, Building, Dorm):
            s.execute(delete(model))
        s.add_all(Building(code=c, name=n, lat=la, lon=lo, source=loc_source) for c, n, la, lo in buildings)
        s.add_all(Dorm(code=c, name=n, lat=la, lon=lo, source=loc_source) for c, n, la, lo in dorms)
        s.add_all(Course(**c.model_dump()) for c in catalog.courses())
        s.flush()
        s.add_all(Section(**x.model_dump()) for x in catalog.sections())


def get_session():
    with SessionLocal() as s:
        yield s
