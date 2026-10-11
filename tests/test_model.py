import numpy as np
import pandas as pd
import pytest

from gridflex.data import DataQualityError
from gridflex.features import FEATURES, forecast_features, series_from_frame, training_features
from gridflex.model import conformal_radius, folds, load_bundle, metrics, predict_bundle, train


def test_features_do_not_see_future_or_latency_window(carbon):
    actual = series_from_frame(carbon)
    origin = pd.Timestamp("2025-04-01", tz="UTC")
    before = forecast_features(actual, origin)
    changed = actual.copy()
    changed.loc[origin - pd.Timedelta(hours=2) :] = 99999
    after = forecast_features(changed, origin)
    pd.testing.assert_frame_equal(before, after)
    assert before.horizon.tolist() == list(range(1, 49))
    assert not {"actual", "forecast", "target"}.intersection(FEATURES)


def test_missing_critical_history_fails_closed(carbon):
    actual = series_from_frame(carbon)
    actual.loc[pd.Timestamp("2025-03-31T21:30Z")] = np.nan
    with pytest.raises(DataQualityError):
        forecast_features(actual, "2025-04-01T00:00Z")


def test_dst_does_not_change_horizon(carbon):
    actual = series_from_frame(carbon)
    result = forecast_features(actual, "2025-03-30T00:00Z")
    assert len(result) == 48
    assert (result.timestamp.diff().dropna() == pd.Timedelta(minutes=30)).all()


def test_walk_forward_has_no_shared_targets(carbon):
    gold, report = training_features(carbon)
    assert report["skipped_origins"] == 0
    previous = None
    for fit, cal, test in folds(gold):
        assert fit.timestamp.max() < cal.origin.min()
        assert cal.timestamp.max() < test.origin.min()
        if previous is not None:
            assert test.origin.min() > previous
        previous = test.origin.min()


def test_conformal_finite_sample_rank():
    assert conformal_radius([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], alpha=0.2) == 9
    with pytest.raises(ValueError):
        conformal_radius([])
    assert metrics([0, 2], [1, 1])["mae"] == 1


def test_real_bundle_hash_and_inference(carbon):
    from pathlib import Path

    bundle = load_bundle(Path("models/production"))
    frame = forecast_features(series_from_frame(carbon), "2025-04-01T00:00Z")
    prediction = predict_bundle(bundle, frame)
    assert len(prediction) == 48
    assert (prediction.lower <= prediction.prediction).all()
    assert (prediction.upper >= prediction.prediction).all()


def test_training_and_mlflow_are_reproducible_contracts(carbon, tmp_path, monkeypatch):
    import mlflow

    # Exercise actual training and a real local tracking store, not mocked logging calls.
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path / 'tracking.db'}")
    monkeypatch.setattr(
        "gridflex.model.PARAMS",
        {"n_estimators": 5, "num_leaves": 7, "n_jobs": 1, "verbosity": -1, "random_state": 42},
    )
    card = train(carbon, tmp_path / "bundle", data_kind="synthetic", track=True)
    assert card["data_kind"] == "synthetic" and len(card["folds"]) == 3
    assert len(card["summary"]) == 5
    best = min(v["mae"] for k, v in card["summary"].items() if k != "lightgbm")
    assert card["candidate_gate_passed"] == (
        card["summary"]["lightgbm"]["mae"] < best and card["summary"]["lightgbm"]["coverage"] >= 0.9
    )
    assert load_bundle(tmp_path / "bundle")["card"]["features"] == FEATURES
    runs = mlflow.search_runs(experiment_names=["uk-grid-flexibility"])
    assert len(runs) == 1 and runs.iloc[0]["status"] == "FINISHED"
    with pytest.raises(ValueError, match="already contains"):
        train(carbon, tmp_path / "bundle", data_kind="synthetic")
