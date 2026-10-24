"""Leave-by time, on-time probability and service alerts.

Walking time is modelled as lognormal around the nominal walk (SIGMA is an ASSUMPTION, not
fitted). Bus legs use live arrivals + the delay model (delay_model.py). Everything returns a
plain-language "why"; probabilities are never 0 or 1.
"""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from statistics import NormalDist
from zoneinfo import ZoneInfo

from clients import transit
from clients.bu_http import CACHE_DIR
from locations import walking_seconds
from optimizer import PACE, hm
from transit_net import near_stops

TZ = ZoneInfo("America/New_York")
SIGMA = 0.2
TARGET_P = 0.90
Z90 = NormalDist().inv_cdf(TARGET_P)
BUS_MIN_WALK_MIN = 12
BUS_HORIZON_H = 4
ASSUMED_BUS_MPS, STOP_DWELL_S = 4.2, 20
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
STORE = CACHE_DIR / "schedules.json"


# ---------- schedule store (generated schedules are looked up by id) ----------
def schedule_id(section_ids: list[str], dorm_id: str | None) -> str:
    return hashlib.sha1(("|".join(sorted(section_ids)) + f"#{dorm_id}").encode()).hexdigest()[:10]


def _read() -> dict:
    try:
        return json.loads(STORE.read_text())
    except (OSError, ValueError):
        return {}


def save_schedule(schedule: dict, dorm_id: str | None, pace: str) -> str:
    sid = schedule_id([s["id"] for s in schedule["sections"]], dorm_id)
    store = _read()
    store.pop(sid, None)
    store[sid] = {"dorm_id": dorm_id, "walking_pace": pace, "schedule": schedule}
    CACHE_DIR.mkdir(exist_ok=True)
    STORE.write_text(json.dumps(dict(list(store.items())[-100:])))
    return sid


def load_schedule(sid: str) -> dict | None:
    return _read().get(sid)


# ---------- walking probability ----------
def p_walk_ok(slack_min: float, walk_min: float) -> float:
    if slack_min <= 0:
        return 0.02
    z = (math.log(slack_min) - math.log(max(walk_min, 1.0))) / SIGMA
    return min(0.98, max(0.02, NormalDist().cdf(z)))


def risk_level(p: float) -> str:
    return "green" if p >= 0.85 else "amber" if p >= 0.5 else "red"


def add_transition_risk(transitions: list[dict]) -> None:
    for t in transitions:
        p = p_walk_ok(t["gap_minutes"], t["walk_minutes"])
        t["p_on_time"] = round(p, 2)
        t["risk"] = risk_level(p)
        t["risk_why"] = (f"{t['gap_minutes']} min between classes vs a walk of about {t['walk_minutes']} min "
                         f"({t['from_building'] or '?'} to {t['to_building'] or '?'}): {label(p)} chance of arriving on time.")


def label(p: float) -> str:
    if p < 0.05:
        return "under 5%"
    if p > 0.95:
        return "over 95%"
    return f"about {round(p * 20) * 5}%"


# ---------- helpers ----------
def _local(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(TZ) if s else None


def _walk_min(a: tuple[float, float], b: tuple[float, float], pace: str) -> float:
    return walking_seconds(*a, *b) * PACE[pace] / 60


def _target_date(day: str, start: str, now: datetime):
    d = now.date() + timedelta(days=(DAYS.index(day) - now.weekday()) % 7)
    at = datetime.combine(d, datetime.min.time(), tzinfo=TZ) + timedelta(minutes=hm(start))
    return at if at > now else at + timedelta(days=7)


def _ride_seconds(net, route_id, o_stop, d_stop, ride_pairs):
    if ride_pairs:
        return sorted(ride_pairs)[len(ride_pairs) // 2], "gateway ETAs for the same vehicle at both stops"
    stops = sorted((rs for rs in net["route_stops"] if rs["route_id"] == route_id), key=lambda r: r["order"])
    idx = {rs["physical_id"]: i for i, rs in enumerate(stops)}
    i, j = idx[o_stop], idx[d_stop]
    dist = sum(walking_seconds(net["stops"][stops[k]["physical_id"]]["lat"], net["stops"][stops[k]["physical_id"]]["lon"],
                               net["stops"][stops[k + 1]["physical_id"]]["lat"], net["stops"][stops[k + 1]["physical_id"]]["lon"]) * 1.3
               for k in range(i, j))  # walking_seconds is numerically meters (x1.3 detour / 1.3 m/s); x1.3 road detour
    return dist / ASSUMED_BUS_MPS + STOP_DWELL_S * (j - i), f"assumed average bus speed of {ASSUMED_BUS_MPS * 3.6:.0f} km/h"


# ---------- leave-by ----------
def leave_by(entry: dict, class_id: str, day: str | None, now: datetime, buildings: dict, dorms: dict,
             net: dict | None, model_getter) -> dict:
    sched = entry["schedule"]
    secs = {s["id"]: s for s in sched["sections"]}
    target = secs.get(class_id)
    if target is None:
        raise KeyError("class not in schedule")
    if not (target["days"] and target["start"] and target["end"]):
        raise ValueError("This section is TBA/online, so there is no fixed time to leave for.")
    pace = entry.get("walking_pace", "normal")
    warnings: list[str] = []

    if day is None:  # next upcoming meeting
        day = min(target["days"], key=lambda d: _target_date(d, target["start"], now))
    if day not in target["days"]:
        raise ValueError(f"{target['course_code']} does not meet on {day}.")
    start_at = _target_date(day, target["start"], now)

    prev = max((s for s in sched["sections"] if s["id"] != class_id and s["start"] and day in s["days"] and hm(s["end"]) <= hm(target["start"])),
               key=lambda s: hm(s["end"]), default=None)
    if prev and prev["building_code"] in buildings:
        o_kind, o_code, o_pt = "class", prev["building_code"], buildings[prev["building_code"]]
        earliest_leave = start_at.replace(hour=0, minute=0) + timedelta(minutes=hm(prev["end"]))
    else:
        o_kind, o_code, o_pt, earliest_leave = "dorm", entry.get("dorm_id"), dorms.get(entry.get("dorm_id")), None
    dest_code = target["building_code"]
    dest_pt = buildings.get(dest_code)
    if o_pt is None or dest_pt is None:
        raise ValueError("Missing location for the start or destination, so a walking time cannot be estimated.")

    W = _walk_min(o_pt, dest_pt, pace)
    lo, hi = W * math.exp(-SIGMA * Z90), W * math.exp(SIGMA * Z90)
    origin_txt = f"your dorm ({o_code})" if o_kind == "dorm" else f"{o_code} (after {prev['course_code']})"

    def mk_walk():
        leave = start_at - timedelta(minutes=math.ceil(max(W, 1) * math.exp(SIGMA * Z90)))
        if earliest_leave and leave < earliest_leave:
            leave = earliest_leave
        p = p_walk_ok((start_at - leave).total_seconds() / 60, W)
        return {"mode": "walk", "leave": leave, "p": p, "why": (
            f"Walking from {origin_txt} to {dest_code} takes about {W:.0f} min (plausible range {lo:.0f}-{hi:.0f} min). "
            f"Leaving then gives {(start_at - leave).total_seconds() / 60:.0f} min, which is {label(p)} likely to be enough.")}

    options = [mk_walk()]
    bus_note = None
    mins_ahead = (start_at - now).total_seconds() / 3600
    if W < BUS_MIN_WALK_MIN:
        bus_note = f"The walk is short ({W:.0f} min), so a bus was not considered."
    elif net is None:
        bus_note = "Bus network data is unavailable, so only walking was considered."
    elif not 0 < mins_ahead <= BUS_HORIZON_H or start_at.date() != now.date():
        bus_note = "Live bus times only cover the next few hours, so only walking was considered for this class."
    else:
        b = _bus_option(net, o_pt, dest_pt, dest_code, start_at, now, pace, earliest_leave, model_getter)
        if isinstance(b, str):
            bus_note = b
        else:
            options.append(b)

    ok = [o for o in options if o["p"] >= TARGET_P]
    best = max(ok, key=lambda o: o["leave"]) if ok else max(options, key=lambda o: o["p"])
    if best["mode"] == "bus" and options[0]["p"] >= TARGET_P and best["leave"] - options[0]["leave"] < timedelta(minutes=3):
        best = options[0]  # bus must buy at least 3 minutes to be worth the complexity
    if best["leave"] < now:
        warnings.append("The recommended leave time has already passed; leave now.")
        best = {**best, "leave": now}
    why = best["why"]
    if best["mode"] == "bus":
        why += f" Walking instead would mean leaving at {options[0]['leave'].strftime('%H:%M')}."
    if bus_note:
        why += " " + bus_note
    return {
        "class_id": class_id, "course_code": target["course_code"], "day": day,
        "class_start": start_at.isoformat(), "leave_at": best["leave"].strftime("%H:%M"), "leave_at_iso": best["leave"].isoformat(),
        "mode": best["mode"], "probability_on_time": round(best["p"], 2), "probability_label": label(best["p"]),
        "origin": {"kind": o_kind, "code": o_code}, "destination": dest_code,
        "walk_minutes": {"median": round(W, 1), "low": round(lo, 1), "high": round(hi, 1)},
        "bus": best.get("bus"), "delay_model": best.get("delay_model"), "why": why, "warnings": warnings,
    }


def _bus_option(net, o_pt, d_pt, dest_code, start_at, now, pace, earliest_leave, model_getter):
    near_o, near_d = dict(near_stops(net, *o_pt, k=3)), dict(near_stops(net, *d_pt, k=3))
    best = None
    for r_id, r in net["routes"].items():
        if not r["is_running"]:
            continue
        rs = {x["physical_id"]: x for x in net["route_stops"] if x["route_id"] == r_id}
        for po, wo in near_o.items():
            for pd_, wd in near_d.items():
                if po in rs and pd_ in rs and rs[po]["order"] < rs[pd_]["order"]:
                    cost = wo + wd
                    if best is None or cost < best[0]:
                        best = (cost, r_id, rs[po], rs[pd_], wo, wd)
    if best is None:
        return "No running shuttle route connects stops near the start and destination."
    _, r_id, rso, rsd, wo_s, wd_s = best
    ao, so = transit.arrivals(rso["id"])
    ad, _ = transit.arrivals(rsd["id"])
    if so != "live" or not ao:
        return "Live bus arrivals are unavailable right now, so only walking was considered."

    def arrs(data, rid):
        return [a for g in (data or {}).get("groups", []) if str(g["route_id"]) == rid for a in g["arrivals"]]

    dest_by_vehicle = {a["vehicle_id"]: a for a in arrs(ad, r_id) if a.get("vehicle_id") is not None and a.get("estimate_at")}
    pairs = []
    for a in arrs(ao, r_id):
        d = dest_by_vehicle.get(a.get("vehicle_id"))
        if d and a.get("estimate_at") and _local(d["estimate_at"]) > _local(a["estimate_at"]):
            pairs.append((_local(d["estimate_at"]) - _local(a["estimate_at"])).total_seconds())
    ride_s, ride_src = _ride_seconds(net, r_id, rso["physical_id"], rsd["physical_id"], pairs)

    walk_o = wo_s * PACE[pace] / 60
    walk_d90 = (wd_s * PACE[pace] / 60) * math.exp(SIGMA * Z90)
    walk_o90 = max(walk_o, 1) * math.exp(SIGMA * Z90)
    model = model_getter()
    cands = []
    for a in arrs(ao, r_id):
        S = _local(a.get("scheduled_at"))
        if S is None or S < now - timedelta(minutes=5):
            continue
        rng = model.range(r_id, rso["physical_id"], S.replace(tzinfo=None))
        arrive_sched = S + timedelta(seconds=ride_s + walk_d90 * 60)
        slack = (start_at - arrive_sched).total_seconds()
        p = model.prob_delay_le(r_id, rso["physical_id"], S.replace(tzinfo=None), slack)
        E = _local(a.get("estimate_at")) if a.get("is_live") else None
        # be at the stop even if the bus runs early (model's 5th percentile) and by the gateway's live ETA
        at_stop = min(S + timedelta(seconds=rng["q05"]), E) if E else S + timedelta(seconds=rng["q05"])
        leave = at_stop - timedelta(minutes=walk_o90)
        if leave < now or (earliest_leave and leave < earliest_leave):
            continue  # that bus has effectively gone, or the previous class is still running
        cands.append((p, leave, S, a, rng))
    if not cands:
        return "No upcoming bus can be caught in time and still reach the class."
    ok = [c for c in cands if c[0] >= TARGET_P]
    p, leave, S, a, rng = max(ok, key=lambda c: c[1]) if ok else max(cands, key=lambda c: c[0])
    E = _local(a.get("estimate_at"))
    eta_txt = (f" The gateway currently predicts it {abs((E - S).total_seconds()) / 60:.0f} min {'late' if E > S else 'early'} (at {E.strftime('%H:%M')})." if E and a.get("is_live")
               else " No live prediction for that trip yet; the posted time is used.")
    rt = lambda k: f"{rng[k] / 60:+.0f}"
    note = f" Note: {delay_note(model)}" if model.synthetic else ""
    stops = net["stops"]
    why = (f"Take shuttle route {r_id} ({net['routes'][r_id]['name']}) from {stops[rso['physical_id']]['name']} (about {walk_o:.0f} min walk) to "
           f"{stops[rsd['physical_id']]['name']}, then walk to {dest_code}. The bus is posted for {S.strftime('%H:%M')}.{eta_txt} "
           f"Ride is about {ride_s / 60:.0f} min ({ride_src}). The delay model expects the bus {rt('q10')} to {rt('q90')} min vs schedule "
           f"(80% range), so arriving on time is {label(p)} likely.{note}")
    return {"mode": "bus", "leave": leave, "p": p, "why": why,
            "bus": {"route_id": r_id, "route_name": net["routes"][r_id]["name"], "board_stop": stops[rso["physical_id"]]["name"],
                    "alight_stop": stops[rsd["physical_id"]]["name"], "scheduled_departure": S.strftime("%H:%M"),
                    "gateway_eta": E.strftime("%H:%M") if E and a.get("is_live") else None, "ride_minutes": round(ride_s / 60),
                    "ride_source": ride_src, "delay_range_seconds": {k: round(rng[k]) for k in ("q10", "q50", "q90")}},
            "delay_model": {"source": model.source, "synthetic": model.synthetic}}


def delay_note(model) -> str:
    from delay_model import SYNTH_NOTE
    return SYNTH_NOTE


# ---------- alerts ----------
def alerts_for(route_ids: list[str], net: dict | None) -> dict:
    out, notes = [], []
    rname = (lambda r: net["routes"][r]["name"]) if net else (lambda r: f"route {r}")
    veh, vs = transit.vehicles()
    if vs == "live" and veh:
        for v in veh.get("vehicles", []):
            if str(v.get("route_id")) in route_ids and v.get("is_delayed"):
                out.append({"kind": "delay", "route_id": str(v["route_id"]), "route_specific": True, "at": v.get("reported_at"),
                            "text": f"A shuttle on {rname(str(v['route_id']))} is flagged as delayed by the gateway.",
                            "why": "Reported by live vehicle tracking (is_delayed)."})
    elif route_ids:
        notes.append("Live vehicle data unavailable; delay alerts could not be checked.")
    if net and route_ids and not any(net["routes"][r]["is_running"] for r in route_ids if r in net["routes"]):
        out.append({"kind": "no_service", "route_specific": True, "text": "None of the shuttle routes serving your dorm and class buildings is running right now.",
                    "why": "All of your routes report is_running = false (it may be normal outside service hours)."})
    notices, ns = transit.notices()
    if ns == "live" and notices:
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        for n in notices.get("notices", []):
            posted = datetime.fromisoformat(n["posted_at"].replace("Z", "+00:00"))
            if posted >= cutoff:
                out.append({"kind": "notice", "route_specific": False, "text": n["text"], "at": n["posted_at"], "url": n.get("source_url"),
                            "why": "Official BU shuttle update from the last 14 days. The gateway does not say which route it applies to."})
    return {"alerts": out, "routes": route_ids, "notes": notes,
            "source_status": {"vehicles": vs, "notices": ns},
            "note_no_route_alerts": "The gateway has no route-tagged service alerts; delay and no-service alerts are derived from live vehicle/route status."}
