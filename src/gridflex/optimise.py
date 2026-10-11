"""Optimal divisible charging under a linear carbon/cost objective; no discharge or V2G."""

from typing import Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChargingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    mode: Literal["replay", "live"] = "replay"
    expected_forecast_id: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    capacity_kwh: float = Field(default=60, gt=0, le=500)
    initial_soc: float = Field(default=0.3, ge=0, le=1)
    target_soc: float = Field(default=0.8, ge=0, le=1)
    max_charge_kw: float = Field(default=7, gt=0, le=350)
    efficiency: float = Field(default=0.9, ge=0.5, le=1)
    available_slots: int = Field(default=48, ge=1, le=48)
    objective: Literal["carbon", "cost", "balanced"] = "carbon"
    carbon_weight: float = Field(default=0.5, ge=0, le=1)
    prices_p_per_kwh: list[float] | None = Field(default=None, max_length=48)

    @model_validator(mode="after")
    def validate_request(self):
        if self.target_soc <= self.initial_soc:
            raise ValueError("Target charge must exceed initial charge")
        if self.prices_p_per_kwh is not None:
            if len(self.prices_p_per_kwh) != self.available_slots:
                raise ValueError("Provide one price per available half-hour slot")
            if not all(np.isfinite(p) and -500 <= p <= 1000 for p in self.prices_p_per_kwh):
                raise ValueError("Prices must be finite and between -500 and 1000 p/kWh")
        if self.objective != "carbon" and self.prices_p_per_kwh is None:
            raise ValueError("Cost and balanced objectives require your own tariff prices")
        return self


def optimise(forecast: pd.DataFrame, request: ChargingRequest) -> dict:
    if len(forecast) < request.available_slots:
        raise ValueError("Not enough forecast slots")
    frame = forecast.iloc[: request.available_slots].copy()
    times = pd.to_datetime(frame.timestamp, utc=True)
    if times.duplicated().any() or not (times.diff().dropna() == pd.Timedelta(minutes=30)).all():
        raise ValueError("Charging requires contiguous half-hour intervals")
    carbon = frame.prediction.to_numpy(dtype=float)
    if not np.isfinite(carbon).all() or (carbon < 0).any():
        raise ValueError("Carbon forecasts must be nonnegative and finite")
    battery_energy = (request.target_soc - request.initial_soc) * request.capacity_kwh
    grid_energy = battery_energy / request.efficiency
    slot_limit = request.max_charge_kw * 0.5
    if grid_energy > request.available_slots * slot_limit + 1e-9:
        raise ValueError("Target charge is infeasible within the selected time and power limits")
    price = None if request.prices_p_per_kwh is None else np.array(request.prices_p_per_kwh)

    def normalise(x):
        return (x - x.min()) / np.ptp(x) if np.ptp(x) else np.zeros(len(x))

    if request.objective == "carbon":
        score = carbon
    elif request.objective == "cost":
        score = price
    else:
        score = request.carbon_weight * normalise(carbon) + (1 - request.carbon_weight) * normalise(price)

    def allocate(order):
        energy, remaining = np.zeros(len(frame)), grid_energy
        for index in order:
            amount = min(slot_limit, max(0, remaining))
            energy[index], remaining = amount, remaining - amount
        return energy

    chosen = allocate(np.argsort(score, kind="stable"))
    immediate = allocate(range(len(frame)))
    carbon_kg, baseline_kg = float(chosen @ carbon / 1000), float(immediate @ carbon / 1000)
    soc = request.initial_soc + np.cumsum(chosen * request.efficiency) / request.capacity_kwh
    return {
        "objective": request.objective,
        "grid_energy_kwh": round(grid_energy, 5),
        "battery_energy_kwh": round(battery_energy, 5),
        "carbon_kg": round(carbon_kg, 5),
        "immediate_carbon_kg": round(baseline_kg, 5),
        "estimated_carbon_reduction_pct": round(100 * (baseline_kg - carbon_kg) / baseline_kg, 2)
        if baseline_kg
        else 0,
        "cost_gbp": round(float(chosen @ price / 100), 4) if price is not None else None,
        "immediate_cost_gbp": round(float(immediate @ price / 100), 4) if price is not None else None,
        "slots": [
            {
                "timestamp": t.isoformat(),
                "grid_kwh": round(float(e), 6),
                "charge_kw": round(float(e * 2), 6),
                "soc": round(float(s), 6),
                "carbon_g_per_kwh": round(float(c), 3),
            }
            for t, e, s, c in zip(times, chosen, soc, carbon, strict=True)
        ],
        "assumptions": [
            "Charge-only, divisible half-hour dispatch with fixed efficiency.",
            "Start at the first forecast slot; deadline is available_slots × 30 minutes later.",
            "Carbon estimates use average grid intensity; these are not verified avoided emissions.",
            "The baseline starts charging immediately with identical energy and power constraints.",
            "No battery degradation, household load, export or physical charger control.",
        ],
    }
