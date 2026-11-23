"""Build the three tables the Power BI report loads, from this repository's own evidence files.

Usage (from the repository root):
    python powerbi/make_powerbi_data.py . powerbi/data

Inputs (all committed in this repository):
    data/reference/carbon.csv                 half-hourly GB carbon intensity, actual and NESO forecast
    docs/evidence/extended-backtest.csv.gz    walk-forward predictions of the candidate and four baselines
    docs/evidence/charging-evaluation.csv     168 simulated charging scenarios
"""
import sys

import pandas as pd

repo, out = sys.argv[1], sys.argv[2]
FMT = "%Y-%m-%d %H:%M"

# 1) Carbon: one row per half hour.
c = pd.read_csv(f"{repo}/data/reference/carbon.csv")
ts = pd.to_datetime(c["timestamp"], utc=True)
carbon = pd.DataFrame(
    {
        "timestamp_utc": ts.dt.strftime(FMT),
        "date": ts.dt.strftime("%Y-%m-%d"),
        "hour": ts.dt.hour,
        "actual_gco2_kwh": c["actual"],
        "neso_forecast_gco2_kwh": c["forecast"],
    }
)
carbon.to_csv(f"{out}/Carbon.csv", index=False)

# 2) Backtest: one row per forecast target and model (long format, so "model" is a column).
b = pd.read_csv(f"{repo}/docs/evidence/extended-backtest.csv.gz")
source_column = {
    "LightGBM (candidate)": "prediction",
    "Persistence": "latest",
    "Weekly seasonal": "target_week_lag",
    "Daily seasonal": "daily_seasonal",
    "Seven-day mean (live)": "seven_day_mean",
}
target = pd.to_datetime(b["timestamp"], utc=True)
frames = []
for model, col in source_column.items():
    d = pd.DataFrame(
        {
            "origin_utc": pd.to_datetime(b["origin"], utc=True).dt.strftime(FMT),
            "target_utc": target.dt.strftime(FMT),
            "target_date": target.dt.strftime("%Y-%m-%d"),
            "fold": b["fold"],
            "horizon_hours": b["horizon"] / 2,
            "model": model,
            "actual_gco2_kwh": b["target"],
            "predicted_gco2_kwh": b[col].round(2),
        }
    )
    d["error"] = (d["predicted_gco2_kwh"] - d["actual_gco2_kwh"]).round(2)
    d["abs_error"] = d["error"].abs()
    d["squared_error"] = (d["error"] ** 2).round(2)
    if col == "prediction":  # only the candidate has prediction intervals
        d["interval_lower"] = b["lower"].round(2)
        d["interval_upper"] = b["upper"].round(2)
        d["inside_interval"] = ((b["target"] >= b["lower"]) & (b["target"] <= b["upper"])).astype("Int64")
    frames.append(d)
backtest = pd.concat(frames, ignore_index=True)
backtest["inside_interval"] = backtest["inside_interval"].astype("Int64")
backtest.to_csv(f"{out}/Backtest.csv", index=False)

# 3) Charging: one row per simulated scenario. Values are kg CO2 on the average-intensity proxy.
ch = pd.read_csv(f"{repo}/docs/evidence/charging-evaluation.csv")
start = pd.to_datetime(ch["origin"], utc=True)
charging = pd.DataFrame(
    {
        "scenario_start_utc": start.dt.strftime(FMT),
        "date": start.dt.strftime("%Y-%m-%d"),
        "start_hour": start.dt.hour,
        "immediate_kg": ch["immediate_proxy_kg"].round(4),
        "scheduled_kg": ch["observed_schedule_proxy_kg"].round(4),
        "seven_day_mean_schedule_kg": ch["seven_day_mean_schedule_proxy_kg"].round(4),
        "perfect_information_kg": ch["perfect_information_proxy_kg"].round(4),
    }
)
charging["saving_kg"] = (charging["immediate_kg"] - charging["scheduled_kg"]).round(4)
charging["result"] = charging["saving_kg"].apply(
    lambda v: "Scheduled better" if v > 0 else ("Same" if v == 0 else "Immediate better")
)
charging.to_csv(f"{out}/Charging.csv", index=False)

print(f"Carbon.csv    {len(carbon):>6} rows")
print(f"Backtest.csv   {len(backtest):>6} rows")
print(f"Charging.csv  {len(charging):>6} rows")
