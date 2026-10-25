"""Bus network helpers built from the real /routes response, plus the user's watch list."""
import json
import time

from clients import transit
from clients.bu_http import CACHE_DIR
from locations import walking_seconds

NEAR_STOP_WALK_S = 8 * 60  # a stop counts as "near" if it is within ~8 minutes' walk
_memo: tuple[float, dict | None] = (0.0, None)


def network() -> dict | None:
    """{'routes': {id: {...}}, 'stops': {physical_id: {name, lat, lon}},
        'route_stops': [{route_id, id, physical_id, order}]} or None if /routes is unavailable."""
    global _memo
    ts, net = _memo
    if net and time.time() - ts < 600:
        return net
    data, _ = transit.routes()
    if not data or "routes" not in data:
        return net
    net = {"routes": {}, "stops": {}, "route_stops": []}
    for r in data["routes"]:
        net["routes"][str(r["id"])] = {"name": r.get("name"), "is_running": bool(r.get("is_running"))}
        for s in r.get("stops", []):
            pid = str(s["physical_stop_id"])
            net["stops"].setdefault(pid, {"name": s["name"], "lat": s["latitude"], "lon": s["longitude"]})
            net["route_stops"].append({"route_id": str(r["id"]), "id": str(s["id"]), "physical_id": pid, "order": s["order"]})
    _memo = (time.time(), net)
    return net


def near_stops(net: dict, lat: float, lon: float, k: int = 2) -> list[tuple[str, float]]:
    """[(physical_stop_id, walk_seconds)] for the k nearest stops within NEAR_STOP_WALK_S."""
    ranked = sorted(((walking_seconds(lat, lon, s["lat"], s["lon"]), pid) for pid, s in net["stops"].items()))
    return [(pid, sec) for sec, pid in ranked[:k] if sec <= NEAR_STOP_WALK_S]


WATCH_PATH = CACHE_DIR / "watch.json"


def set_watch(dorm_id: str | None, building_codes: list[str]) -> dict:
    CACHE_DIR.mkdir(exist_ok=True)
    w = {"dorm_id": dorm_id, "building_codes": sorted(set(building_codes))}
    WATCH_PATH.write_text(json.dumps(w))
    return w


def get_watch() -> dict | None:
    try:
        return json.loads(WATCH_PATH.read_text())
    except (OSError, ValueError):
        return None


def watched(net: dict, dorms: dict, buildings: dict) -> dict:
    """Stops/routes relevant to the user. dorms/buildings: code -> (lat, lon).
    With no watch registered yet, every dorm and building counts (so data still accrues)."""
    w = get_watch()
    if w:
        d_codes = [w["dorm_id"]] if w.get("dorm_id") in dorms else []
        b_codes = [c for c in w["building_codes"] if c in buildings]
    else:
        d_codes, b_codes = list(dorms), list(buildings)
    near_dorm = {p for c in d_codes for p, _ in near_stops(net, *dorms[c])}
    near_bldg = {p for c in b_codes for p, _ in near_stops(net, *buildings[c])}
    physical = near_dorm | near_bldg
    by_route: dict[str, set[str]] = {}
    for rs in net["route_stops"]:
        by_route.setdefault(rs["route_id"], set()).add(rs["physical_id"])
    # the user's routes serve a stop near the dorm AND a stop near a class building
    routes = sorted(r for r, ps in by_route.items() if ps & near_dorm and ps & near_bldg)
    return {"registered": bool(w), "physical_stops": sorted(physical), "routes": routes,
            "route_stops": [rs for rs in net["route_stops"] if rs["physical_id"] in physical and net["routes"][rs["route_id"]]["is_running"]]}
