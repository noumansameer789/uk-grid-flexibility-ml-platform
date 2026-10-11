"""Render a measured-data walkthrough, not a recording of a deployed website.

Run with the development dependencies and ffmpeg installed.
"""

import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from gridflex.optimise import ChargingRequest, optimise

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
replay = json.loads((ROOT / "models/production/replay.json").read_text())
card = json.loads((ROOT / "models/production/model_card.json").read_text())
frame = pd.DataFrame(replay["slots"])
plan = optimise(frame, ChargingRequest())
plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 13,
        "text.color": "#eef4fa",
        "axes.labelcolor": "#b3c5d5",
        "xtick.color": "#b3c5d5",
        "ytick.color": "#b3c5d5",
        "axes.edgecolor": "#304556",
        "savefig.facecolor": "#0b1520",
    }
)


def page(title, subtitle):
    fig = plt.figure(figsize=(12.8, 7.2), dpi=100, facecolor="#0b1520")
    fig.text(0.065, 0.93, "GRIDFLEX GB  /  NOUMAN SAMEER", color="#57d7b3", fontsize=13, weight="bold")
    fig.text(0.065, 0.86, title, fontsize=26, weight="bold")
    fig.text(0.065, 0.81, subtitle, fontsize=12, color="#b3c5d5")
    fig.text(
        0.065,
        0.045,
        "Recorded data walkthrough · historical replay · research portfolio · no hardware control",
        fontsize=10,
        color="#94a9ba",
    )
    return fig


def chart(fig, position):
    ax = fig.add_axes(position, facecolor="#102333")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.15)
    return ax


fig = page(
    "Forecast the next 24 hours",
    "Retrospective NESO replay starting 00:00 UTC on 21 September 2026; reconstructed later.",
)
ax = chart(fig, [0.085, 0.24, 0.86, 0.49])
x = np.arange(48) / 2
ax.fill_between(x, frame.lower, frame.upper, color="#57d7b3", alpha=0.18, label="Nominal 90% interval")
ax.plot(x, frame.prediction, color="#57d7b3", linewidth=2.7, label="LightGBM forecast")
ax.plot(x, frame.actual, color="#e2bc70", linewidth=2, label="Subsequently observed actual")
ax.set(xlabel="Hours after issue time (UTC)", ylabel="Carbon intensity (gCO₂/kWh)", xlim=(0, 23.5))
ax.legend(loc="upper left", facecolor="#102333", edgecolor="#304556", fontsize=10)
fig.text(
    0.085, 0.13, "No future actuals or reanalysis weather enter the model's issue-time features.", fontsize=15
)
fig.savefig(OUT / "01-forecast.png")
plt.close(fig)

fig = page(
    "Meet the same charging requirement",
    "60 kWh battery · 30% → 80% charge · 7 kW limit · 90% efficiency · 24-hour deadline",
)
ax = chart(fig, [0.085, 0.32, 0.86, 0.40])
bars = [slot["charge_kw"] for slot in plan["slots"]]
ax.bar(x, bars, width=0.44, color="#57d7b3")
ax.set(
    xlabel="Hours after issue time (UTC)",
    ylabel="Scheduled charging power (kW)",
    ylim=(0, 8),
    xlim=(-0.5, 24),
)
fig.text(
    0.085,
    0.18,
    f"{plan['grid_energy_kwh']:.2f} kWh from grid   →   {plan['battery_energy_kwh']:.1f} kWh stored",
    fontsize=18,
    weight="bold",
)
fig.text(
    0.085,
    0.115,
    f"Forecast-weighted carbon: {plan['carbon_kg']:.2f} kg vs {plan['immediate_carbon_kg']:.2f} kg for immediate charging.",
    fontsize=14,
)
fig.savefig(OUT / "02-charging.png")
plt.close(fig)

fig = page(
    "Measure the model against baselines",
    "9,792 real half-hours · three walk-forward test windows · no random train/test split",
)
ax = chart(fig, [0.26, 0.35, 0.64, 0.40])
names = ["LightGBM", "Persistence", "Weekly seasonal", "Daily seasonal", "Seven-day mean"]
values = [
    card["summary"][k]["mae"]
    for k in ("lightgbm", "persistence", "weekly_seasonal", "daily_seasonal", "seven_day_mean")
]
ax.barh(names, values, color=["#6b849c", "#6b849c", "#6b849c", "#6b849c", "#57d7b3"], height=0.55)
ax.invert_yaxis()
ax.set(xlabel="Walk-forward MAE (gCO₂/kWh) — lower is better", xlim=(0, 58))
for i, value in enumerate(values):
    ax.text(value + 1, i, f"{value:.2f}", va="center", fontsize=14)
fig.text(0.085, 0.22, "A simple seven-day mean beats LightGBM", fontsize=22, color="#e2bc70", weight="bold")
fig.text(0.085, 0.15, "Intervals covered 86.3% of observations; the 90% target was missed.", fontsize=15)
fig.text(
    0.085,
    0.10,
    "Overlapping forecast horizons produce correlated errors. Live performance is still accumulating.",
    fontsize=12,
    color="#b3c5d5",
)
fig.savefig(OUT / "03-evaluation.png")
plt.close(fig)

fig = page(
    "An inspectable engineering workflow",
    "Source snapshots, predictions and experiment records are supplied with the code.",
)
items = [
    ("COLLECT", "NESO + Open-Meteo; validated raw and cleaned layers"),
    ("EVALUATE", "Purged time-series splits; conformal intervals; MLflow"),
    ("SERVE", "FastAPI + dashboard; constrained charging; explicit source failures"),
    ("OBSERVE", "Issued forecasts; delayed actuals; drift and performance alerts"),
    ("DEPLOY", "Docker + Actions + Azure Terraform; account activation still required"),
]
for i, (label, text) in enumerate(items):
    y = 0.70 - 0.105 * i
    fig.text(0.085, y, label, color="#57d7b3", weight="bold", fontsize=14)
    fig.text(0.245, y, text, fontsize=14)
fig.text(
    0.085,
    0.13,
    "Regression tests, race-condition checks and an explicit failed model-promotion gate.",
    fontsize=15,
)
fig.savefig(OUT / "04-workflow.png")
plt.close(fig)

frames = sorted(OUT.glob("0[1-4]-*.png"))
manifest = OUT / "demo-frames.txt"
manifest.write_text(
    "\n".join(f"file '{p.name}'\nduration 7" for p in frames) + f"\nfile '{frames[-1].name}'\n"
)
subprocess.run(
    [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(manifest),
        "-vf",
        "fps=25",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(OUT / "gridflex-walkthrough.mp4"),
    ],
    check=True,
)
manifest.unlink()
print("Rendered four measured-data figures and a 28-second walkthrough video.")
