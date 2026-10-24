"""Background logger: every 2 minutes, store predicted vs scheduled arrival times for stops
near the user's dorm and class buildings into transit_log. Only LIVE responses are logged
(never cached/fixture data, which would pollute the delay statistics)."""
import json
import os
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import func, select

import db
from clients import transit
from transit_net import network, watched

STATE: dict = {"last_run": None, "last_logged": 0, "last_error": None, "enabled": False}


def _utc(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc).replace(tzinfo=None)


def log_once() -> dict:
    net = network()
    if not net:
        STATE.update(last_run=datetime.now(timezone.utc).isoformat(), last_logged=0, last_error="route network unavailable")
        return {"logged": 0}
    with db.SessionLocal() as s:
        dorms = {d.code: (d.lat, d.lon) for d in s.scalars(select(db.Dorm))}
        blds = {b.code: (b.lat, b.lon) for b in s.scalars(select(db.Building))}
    targets = watched(net, dorms, blds)["route_stops"]
    rows, skipped = [], 0
    obs = datetime.now(timezone.utc).replace(tzinfo=None)
    for rs in targets:
        data, status = transit.arrivals(rs["id"])
        if status != "live" or not data or data.get("stale"):
            skipped += 1
            continue
        for g in data.get("groups", []):
            for a in g.get("arrivals", []):
                pred, sched = _utc(a.get("estimate_at")), _utc(a.get("scheduled_at"))
                if pred is None or sched is None:  # untracked arrivals have no prediction
                    continue
                rows.append(db.TransitLog(
                    endpoint="/api/v1/transit/bus/stops/{stop_id}/arrivals", stop_id=rs["physical_id"],
                    route_id=rs["route_id"], route_stop_id=rs["id"], vehicle_id=None if a.get("vehicle_id") is None else str(a["vehicle_id"]),
                    observed_at=obs, scheduled_at=sched, predicted_at=pred, lead_seconds=int((pred - obs).total_seconds()),
                    delay_seconds=int((pred - sched).total_seconds()), is_live=bool(a.get("is_live")), payload=json.dumps(a)))
    with db.SessionLocal() as s, s.begin():
        s.add_all(rows)
    STATE.update(last_run=datetime.now(timezone.utc).isoformat(), last_logged=len(rows),
                 last_error=f"{skipped} stop(s) skipped (not live)" if skipped else None)
    return {"logged": len(rows), "skipped": skipped, "polled": len(targets)}


def _safe():
    try:
        log_once()
    except Exception as e:  # keep the scheduler alive; never log request details
        STATE["last_error"] = type(e).__name__


def start() -> BackgroundScheduler | None:
    if os.environ.get("COMPASS_LOGGER", "1") == "0":
        return None
    sch = BackgroundScheduler(daemon=True)
    sch.add_job(_safe, "interval", minutes=2, next_run_time=datetime.now(), max_instances=1, coalesce=True)
    sch.start()
    STATE["enabled"] = True
    return sch


def total_rows() -> int:
    with db.SessionLocal() as s:
        return s.scalar(select(func.count()).select_from(db.TransitLog)) or 0
