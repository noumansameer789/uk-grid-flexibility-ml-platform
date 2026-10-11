import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from gridflex.optimise import ChargingRequest, optimise


def example(values):
    return pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-01-01", periods=len(values), freq="30min", tz="UTC"),
            "prediction": values,
        }
    )


def test_carbon_dispatch_meets_energy_and_power_limits():
    req = ChargingRequest(
        capacity_kwh=10, initial_soc=0, target_soc=0.9, max_charge_kw=5, efficiency=0.9, available_slots=6
    )
    out = optimise(example([500, 400, 300, 200, 100, 50]), req)
    assert sum(x["grid_kwh"] for x in out["slots"]) == pytest.approx(10)
    assert out["slots"][-1]["soc"] == pytest.approx(0.9)
    assert all(0 <= x["charge_kw"] <= 5 for x in out["slots"])
    assert out["carbon_kg"] <= out["immediate_carbon_kg"]
    assert [x["charge_kw"] for x in out["slots"]] == [0, 0, 5, 5, 5, 5]


def test_infeasible_target_rejected():
    with pytest.raises(ValueError, match="infeasible"):
        optimise(example([100] * 4), ChargingRequest(available_slots=4, max_charge_kw=1))


@pytest.mark.parametrize(
    "payload",
    [
        {"target_soc": 0.1},
        {"efficiency": float("nan")},
        {"objective": "cost"},
        {"available_slots": 2, "prices_p_per_kwh": [1]},
        {"available_slots": 2, "prices_p_per_kwh": [float("inf"), 2]},
    ],
)
def test_invalid_requests(payload):
    with pytest.raises(ValidationError):
        ChargingRequest(**payload)


def test_negative_prices_do_not_overcharge():
    req = ChargingRequest(
        capacity_kwh=10,
        initial_soc=0,
        target_soc=0.2,
        efficiency=1,
        available_slots=4,
        max_charge_kw=4,
        objective="cost",
        prices_p_per_kwh=[5, -10, -5, 20],
    )
    r = optimise(example([100] * 4), req)
    assert r["slots"][1]["grid_kwh"] == 2 and r["grid_energy_kwh"] == 2
    assert r["cost_gbp"] == -0.2


def test_balanced_dispatch_matches_linear_program():
    from scipy.optimize import linprog

    carbon = np.array([90, 400, 230, 180, 50, 300])
    prices = np.array([40, 5, 20, 25, 45, 10])
    req = ChargingRequest(
        capacity_kwh=10,
        initial_soc=0,
        target_soc=0.6,
        efficiency=1,
        available_slots=6,
        max_charge_kw=4,
        objective="balanced",
        prices_p_per_kwh=prices.tolist(),
    )
    r = optimise(example(carbon), req)
    score = 0.5 * (carbon - carbon.min()) / np.ptp(carbon) + 0.5 * (prices - prices.min()) / np.ptp(prices)
    optimal = linprog(score, A_eq=np.ones((1, 6)), b_eq=[6], bounds=[(0, 2)] * 6, method="highs")
    assert optimal.success
    assert np.array([x["grid_kwh"] for x in r["slots"]]) @ score == pytest.approx(optimal.fun)


def test_noncontiguous_schedule_rejected():
    f = example([100] * 5).drop(index=1)
    with pytest.raises(ValueError, match="contiguous"):
        optimise(f, ChargingRequest(available_slots=4))
