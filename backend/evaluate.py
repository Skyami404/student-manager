"""Compare the CP-SAT optimizer with two baselines on 50 simulated course requests.
Run from backend/:  python evaluate.py
All data is the SYNTHETIC sample catalog, so results say nothing about real BU offerings."""
import json
import random
import statistics as st
import time
from pathlib import Path

from baselines import greedy_first_fit, random_valid
from clients.catalog import SampleCatalogSource
from locations import load_locations
from optimizer import Ctx, ScheduleRequest, generate, score, validate

LABEL = "evaluated on synthetic sample catalog"
N, SEED = 50, 42


def make_requests(courses, rng):
    codes = [c.code for c in courses]
    cred = {c.code: c.credits for c in courses}
    reqs = []
    while len(reqs) < N:
        required = rng.sample(codes, rng.choice([3, 4]))
        if sum(cred[c] for c in required) > 16:
            continue
        optional = rng.sample([c for c in codes if c not in required], rng.choice([3, 4, 5]))
        reqs.append(ScheduleRequest(
            required=required, optional=optional, min_credits=14, max_credits=18,
            dorm_id=rng.choice(["WAR", "SV1", "SV2", "MYL", "CLF", "RCH", "DAN", "SHI"]),
            earliest_start=rng.choice(["08:00", "09:00", "10:00"]), latest_end=rng.choice(["17:00", "18:00"]),
            walking_pace=rng.choice(["slow", "normal", "fast"]), time_limit_s=5))
    return reqs


def main():
    cat = SampleCatalogSource()
    courses, sections = cat.courses(), cat.sections()
    cmap = {c.code: c for c in courses}
    b, d, _ = load_locations()
    coords = {c: (la, lo) for c, _, la, lo in b}
    dorms = {c: (la, lo) for c, _, la, lo in d}
    rng = random.Random(SEED)
    rows, check_fail = [], 0

    for i, req in enumerate(make_requests(courses, rng)):
        ctx = Ctx(req, coords, dorms[req.dorm_id], sections)
        row = {"request": i, "required": req.required, "optional": req.optional, "dorm": req.dorm_id}
        t = time.perf_counter()
        res = generate(courses, sections, req, coords, dorms[req.dorm_id])
        row["optimizer_ms"] = (time.perf_counter() - t) * 1000
        row["optimizer_schedules"] = len(res["schedules"])
        out = {}
        if res["schedules"]:
            top = res["schedules"][0]
            check_fail += not all(s["metrics"]["objective_check"] for s in res["schedules"])
            from clients.catalog import Section
            secs = [Section(**s) for s in top["sections"]]
            out["optimizer"] = (secs, row["optimizer_ms"])
        t = time.perf_counter()
        r = random_valid(cmap, sections, req, random.Random(SEED + i))
        out["random"] = (r, (time.perf_counter() - t) * 1000) if r else None
        t = time.perf_counter()
        g = greedy_first_fit(cmap, sections, req)
        out["greedy"] = (g, (time.perf_counter() - t) * 1000) if g else None
        for name in ("optimizer", "random", "greedy"):
            o = out.get(name)
            if not o:
                row[name] = None
                continue
            secs, ms = o
            why = validate(secs, cmap, sections, req)
            assert why is None, f"{name} produced an invalid schedule on request {i}: {why}"
            m = score(secs, ctx)
            row[name] = {k: m[k] for k in ("tight_transitions", "travel_minutes", "meal_window_days", "class_days", "cost")} | {
                "no_meal_window_days": m["class_days"] - m["meal_window_days"], "ms": ms}
        assert row["optimizer"] or not (row["random"] or row["greedy"]), f"optimizer missed a feasible request {i}"
        rows.append(row)

    feasible = [r for r in rows if r["optimizer"]]
    common = [r for r in feasible if r["random"] and r["greedy"]]
    methods = ["optimizer", "random", "greedy"]

    def avg(rs, m, k):
        return st.mean(r[m][k] for r in rs) if rs else float("nan")

    summary = {}
    for m in methods:
        summary[m] = {
            "valid_schedules": f"{sum(1 for r in rows if r[m])}/{len(rows)}",
            **{k: round(avg(common, m, k), 2) for k in ("tight_transitions", "travel_minutes", "meal_window_days", "class_days", "no_meal_window_days", "cost", "ms")},
        }
    print(f"\nSchedule optimizer vs baselines: {LABEL}")
    print(f"{N} simulated requests (seed {SEED}); metrics averaged over the {len(common)} requests where all three methods found a valid schedule.")
    print("Lower is better for tight, travel, cost. Meal days = class days with a 30+ min free block in 11:00-14:00; no-lunch days = class days without one.\n")
    hdr = f"{'method':<10}{'valid':>8}{'tight':>8}{'travel min':>12}{'meal days':>11}{'class days':>12}{'no-lunch days':>15}{'cost':>9}{'ms':>9}"
    print(hdr + "\n" + "-" * len(hdr))
    for m in methods:
        s = summary[m]
        print(f"{m:<10}{s['valid_schedules']:>8}{s['tight_transitions']:>8}{s['travel_minutes']:>12}{s['meal_window_days']:>11}{s['class_days']:>12}{s['no_meal_window_days']:>15}{s['cost']:>9}{s['ms']:>9}")
    print(f"\ndistinct schedules returned by optimizer (target 3): mean {st.mean(r['optimizer_schedules'] for r in rows):.2f}")
    print(f"solver cost == recomputed cost on every returned schedule: {'yes' if not check_fail else f'NO ({check_fail} mismatches)'}")
    print("Note: 'cost' is the optimizer's own weighted objective (meal reward makes it negative), so it favors the optimizer by design; the other columns are raw metrics.")

    Path(__file__).with_name("eval_results.json").write_text(json.dumps(
        {"label": LABEL, "synthetic_catalog": True, "n_requests": N, "seed": SEED, "common_subset_size": len(common),
         "summary_common_subset": summary, "solver_cost_matches_recomputed": check_fail == 0, "per_request": rows}, indent=1))


if __name__ == "__main__":
    main()
