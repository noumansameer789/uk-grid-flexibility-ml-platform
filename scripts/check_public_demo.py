"""Read-only public health probe and timestamped prospective forecast capture."""

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

BASE = "https://nouman-gridflex-gb.nimblepeony1.chatgpt.site"
out = Path("reports/public-probe")
out.mkdir(parents=True, exist_ok=True)
for endpoint in ["health", "forecast"]:
    request = Request(
        BASE + "/api/" + endpoint,
        headers={
            "User-Agent": "GridFlexHealthCheck/1.0 (+https://github.com/noumansameer789/uk-grid-flexibility-ml-platform)",
            "Accept": "application/json",
        },
    )
    with urlopen(request, timeout=30) as response:
        data = json.load(response)
    (out / (endpoint + ".json")).write_text(json.dumps(data, indent=2))
    if endpoint == "health":
        assert data["status"] == "ok"
    else:
        assert len(data["slots"]) == 48 and data["model"] == "seven_day_mean"
        origin = datetime.fromisoformat(data["issued_at"].replace("Z", "+00:00"))
        assert 0 < (origin - datetime.now(UTC)).total_seconds() <= 1800
        assert all(0 <= row["carbon"] <= 1500 for row in data["slots"])
payload = {
    "battery_kwh": 14.4,
    "power_kw": 7.2,
    "efficiency": 0.9,
    "available_hours": 24,
    "carbon_weight": 1,
    "tariff": "flat",
    "flat_pence": 25,
}
headers = {"User-Agent": "GridFlexHealthCheck/1.0", "Content-Type": "application/json"}
with urlopen(
    Request(BASE + "/api/schedule", data=json.dumps(payload).encode(), headers=headers), timeout=30
) as response:
    plan = json.load(response)
assert math.isclose(sum(s["grid_kwh"] for s in plan["slots"]) * 0.9, 14.4, abs_tol=1e-7)
assert all(0 <= s["grid_kwh"] <= 3.6 + 1e-9 for s in plan["slots"])
assert plan["predicted_carbon_kg"] <= plan["immediate_carbon_kg"] + 1e-7
(out / "schedule.json").write_text(json.dumps(plan, indent=2))
try:
    invalid = {**payload, "battery_kwh": 100, "available_hours": 0.5}
    with urlopen(
        Request(BASE + "/api/schedule", data=json.dumps(invalid).encode(), headers=headers), timeout=30
    ):
        raise AssertionError("Infeasible request was accepted")
except HTTPError as exc:
    assert exc.code == 422, f"Expected 422, got {exc.code}"
(out / "receipt.json").write_text(json.dumps({"checked_at": datetime.now(UTC).isoformat(), "base": BASE}))
print("Public health, live forecast, feasible scheduling and 422 refusal passed.")
