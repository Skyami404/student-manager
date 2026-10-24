"""Bus delay model: quantile gradient boosting on transit_log.

Target: delay in seconds = predicted_at - scheduled_at (negative = early), taken from the LAST
live prediction seen before each bus arrived (0 <= lead <= 150 s). The gateway exposes no
realized arrival time, so this is the closest valid "actual" available.
Features: hour of day, day of week, route, stop. Baseline: the posted schedule (delay = 0).

If transit_log holds too little data (see MIN_REAL_TRIPS / MIN_REAL_DAYS) the model is trained on
SYNTHETIC data from synthetic_dataset() and every output carries synthetic=True.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sqlalchemy import select

import db

TZ = ZoneInfo("America/New_York")
QUANTILES = [0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95]
FEATURES = ["hour", "dow", "route", "stop"]
MIN_REAL_TRIPS = 500
MIN_REAL_DAYS = 3
SYNTH_NOTE = "SYNTHETIC placeholder delays (not enough logged transit data yet); not real BU performance."


# ---------- data ----------
def load_real() -> pd.DataFrame:
    """One row per bus trip: the latest live prediction made 0-150 s before predicted arrival."""
    with db.SessionLocal() as s:
        rows = s.execute(select(
            db.TransitLog.stop_id, db.TransitLog.route_id, db.TransitLog.scheduled_at,
            db.TransitLog.delay_seconds, db.TransitLog.lead_seconds,
        ).where(db.TransitLog.is_live.is_(True), db.TransitLog.lead_seconds.between(0, 150))).all()
    df = pd.DataFrame(rows, columns=["stop", "route", "sched", "delay", "lead"])
    if df.empty:
        return pd.DataFrame(columns=["time", *FEATURES, "delay"])
    df = df.sort_values("lead").drop_duplicates(["stop", "route", "sched"])  # smallest lead per trip
    t = pd.to_datetime(df["sched"]).dt.tz_localize("UTC").dt.tz_convert(TZ).dt.tz_localize(None)
    out = pd.DataFrame({"time": t, "route": df["route"].astype(str), "stop": df["stop"].astype(str),
                        "delay": df["delay"].astype(float)})
    return add_time_features(out).sort_values("time").reset_index(drop=True)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    df["hour"] = df["time"].dt.hour + df["time"].dt.minute / 60
    df["dow"] = df["time"].dt.dayofweek
    return df


def synthetic_dataset(route_stops: list[tuple[str, str]] | None = None, days: int = 45, seed: int = 0) -> pd.DataFrame:
    """SYNTHETIC delays. Invented pattern: rush hours and weekdays are slower, one route runs
    later than another, delay grows along the route, right-skewed noise, occasional big delays."""
    rng = np.random.default_rng(seed)
    pairs = list(dict.fromkeys(route_stops or []))[:12] or [("1", "1"), ("1", "3"), ("1", "13"), ("4", "25"), ("4", "26"), ("2", "40")]
    start = pd.Timestamp("2026-08-24")
    recs = []
    for d in range(days):
        day = start + pd.Timedelta(days=d)
        for h in np.arange(7, 23, 0.5):
            t = day + pd.Timedelta(hours=float(h))
            rush = np.exp(-((h - 8.5) ** 2) / 2) + np.exp(-((h - 17) ** 2) / 2)
            for k, (route, stop) in enumerate(pairs):
                base = 60 + 240 * rush * (day.dayofweek < 5) + 40 * (route == "1") + 25 * (k % 4)
                delay = -90 + rng.lognormal(np.log(base), 0.6)
                if rng.random() < 0.03:
                    delay += rng.uniform(300, 900)
                recs.append((t, route, stop, delay))
    return add_time_features(pd.DataFrame(recs, columns=["time", "route", "stop", "delay"]))


def training_data(route_stops: list[tuple[str, str]] | None = None) -> tuple[pd.DataFrame, str, dict]:
    real = load_real()
    days = (real["time"].max() - real["time"].min()).days + 1 if len(real) else 0
    info = {"real_trips": len(real), "real_days": int(days), "min_trips": MIN_REAL_TRIPS, "min_days": MIN_REAL_DAYS}
    if len(real) >= MIN_REAL_TRIPS and days >= MIN_REAL_DAYS:
        return real, "real", info
    return synthetic_dataset(route_stops), "synthetic", info


# ---------- model ----------
def _pipe(q: float) -> Pipeline:
    pre = ColumnTransformer([
        ("num", "passthrough", ["hour", "dow"]),
        ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=np.nan), ["route", "stop"]),
    ])
    hgb = HistGradientBoostingRegressor(loss="quantile", quantile=q, max_iter=120, learning_rate=0.08,
                                        max_depth=4, min_samples_leaf=20, categorical_features=[2, 3], random_state=0)
    return Pipeline([("pre", pre), ("m", hgb)])


@dataclass
class DelayModel:
    pipes: dict
    source: str            # "real" | "synthetic"
    n_train: int
    trained_at: float

    @property
    def synthetic(self) -> bool:
        return self.source == "synthetic"

    def quantiles(self, df: pd.DataFrame) -> np.ndarray:
        """(n, len(QUANTILES)) delay seconds, forced non-decreasing across quantiles."""
        return np.sort(np.column_stack([self.pipes[q].predict(df[FEATURES]) for q in QUANTILES]), axis=1)

    def range(self, route: str, stop: str, when_local) -> dict:
        t = pd.Timestamp(when_local)
        row = pd.DataFrame({"hour": [t.hour + t.minute / 60], "dow": [t.dayofweek], "route": [str(route)], "stop": [str(stop)]})
        qs = self.quantiles(row)[0]
        return {f"q{int(q * 100):02d}": float(v) for q, v in zip(QUANTILES, qs)} | {"synthetic": self.synthetic, "source": self.source}

    def prob_delay_le(self, route: str, stop: str, when_local, x_seconds: float) -> float:
        """P(delay <= x): piecewise-linear CDF through the predicted quantiles, never 0 or 1."""
        r = self.range(route, stop, when_local)
        xs = [r[f"q{int(q * 100):02d}"] for q in QUANTILES]
        if x_seconds < xs[0]:
            return 0.03
        if x_seconds > xs[-1]:
            return 0.97
        return float(np.interp(x_seconds, xs, QUANTILES))


def fit(df: pd.DataFrame, source: str) -> DelayModel:
    pipes = {q: _pipe(q).fit(df[FEATURES], df["delay"]) for q in QUANTILES}
    return DelayModel(pipes, source, len(df), time.time())


_cached: DelayModel | None = None


def get_model(route_stops=None, max_age_s: float = 3600) -> DelayModel:
    global _cached
    if _cached is None or time.time() - _cached.trained_at > max_age_s:
        df, source, _ = training_data(route_stops)
        _cached = fit(df, source)
    return _cached


def status() -> dict:
    _, source, info = training_data()
    return {"source": source, "synthetic": source == "synthetic", **info,
            "note": SYNTH_NOTE if source == "synthetic" else "Trained on logged BU shuttle predictions."}


# ---------- evaluation ----------
def evaluate_model(df: pd.DataFrame, source: str, train_frac: float = 0.7, seed: int = 0) -> dict:
    """Time-based split (train on the earliest 70%, test on the latest 30%)."""
    df = df.sort_values("time").reset_index(drop=True)
    cut = int(len(df) * train_frac)
    tr, te = df.iloc[:cut], df.iloc[cut:]
    model = fit(tr, source)
    Q = model.quantiles(te)
    y = te["delay"].to_numpy()
    med = Q[:, QUANTILES.index(0.5)]
    err_model, err_sched = np.abs(y - med), np.abs(y)
    err_const = np.abs(y - tr["delay"].median())
    rng = np.random.default_rng(seed)
    boots = [(err_sched[i].mean() - err_model[i].mean()) for i in (rng.integers(0, len(y), len(y)) for _ in range(300))]
    cover = {f"q{int(q * 100):02d}": float((y <= Q[:, i]).mean()) for i, q in enumerate(QUANTILES)}
    i = QUANTILES.index
    return {
        "data_source": source, "synthetic": source == "synthetic",
        "label": "SYNTHETIC delay data: shows the pipeline works, not real BU performance" if source == "synthetic"
                 else "real logged BU shuttle data",
        "n_train": int(len(tr)), "n_test": int(len(te)),
        "train_period": [str(tr["time"].min()), str(tr["time"].max())], "test_period": [str(te["time"].min()), str(te["time"].max())],
        "mae_seconds": {"model_median": float(err_model.mean()), "baseline_posted_schedule_zero_delay": float(err_sched.mean()),
                        "baseline_train_median_constant": float(err_const.mean())},
        "mae_improvement_vs_schedule_seconds": float(err_sched.mean() - err_model.mean()),
        "mae_improvement_ci95_seconds": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
        "calibration": {"nominal_vs_observed_below_quantile": {k: [float(q), round(cover[k], 3)] for k, q in zip(cover, QUANTILES)},
                        "interval_5_95": {"nominal": 0.90, "observed": float(((y >= Q[:, i(0.05)]) & (y <= Q[:, i(0.95)])).mean())},
                        "interval_10_90": {"nominal": 0.80, "observed": float(((y >= Q[:, i(0.10)]) & (y <= Q[:, i(0.90)])).mean())},
                        "mean_width_10_90_seconds": float((Q[:, i(0.90)] - Q[:, i(0.10)]).mean())},
    }
