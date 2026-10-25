"""Delay model on SYNTHETIC data only (the pipeline, not real shuttle accuracy)."""
import pandas as pd
import pytest

import delay_model as dm


@pytest.fixture(scope="module")
def model_and_data():
    df = dm.synthetic_dataset(days=14)
    return dm.fit(df, "synthetic"), df


def test_quantiles_never_cross_and_are_labelled_synthetic(model_and_data):
    model, _ = model_and_data
    rng = model.range("1", "1", pd.Timestamp("2026-10-26 08:30"))
    ordered = [rng[f"q{int(q * 100):02d}"] for q in dm.QUANTILES]
    assert ordered == sorted(ordered)
    assert rng["synthetic"] is True and rng["source"] == "synthetic"


def test_probability_of_arriving_in_time_rises_with_slack_and_is_never_certain(model_and_data):
    model, _ = model_and_data
    when = pd.Timestamp("2026-10-26 17:00")
    probs = [model.prob_delay_le("1", "1", when, slack) for slack in (-600, 0, 120, 300, 900)]
    assert probs == sorted(probs)
    assert 0 < min(probs) and max(probs) < 1


def test_time_split_evaluation_reports_baselines_and_calibration(model_and_data):
    _, df = model_and_data
    result = dm.evaluate_model(df, "synthetic")
    assert result["synthetic"] is True and "SYNTHETIC" in result["label"]
    assert result["n_train"] > result["n_test"] > 0
    assert result["train_period"][1] <= result["test_period"][0]  # train strictly before test: no leakage
    assert set(result["mae_seconds"]) >= {"model_median", "baseline_posted_schedule_zero_delay"}
    assert 0.3 < result["calibration"]["nominal_vs_observed_below_quantile"]["q50"][1] < 0.7
