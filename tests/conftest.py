import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def carbon():
    """Synthetic test fixture only; never reported as observed GB data."""
    t = pd.date_range("2025-01-01", periods=150 * 48, freq="30min", tz="UTC")
    n = np.arange(len(t))
    y = 130 + 35 * np.sin(n / 48 * 2 * np.pi) + 18 * np.cos(n / 336 * 2 * np.pi)
    return pd.DataFrame({"timestamp": t, "end": t + pd.Timedelta(minutes=30), "actual": y, "forecast": y + 5})


@pytest.fixture
def carbon_payload():
    return {
        "data": [
            {
                "from": "2026-01-01T00:00Z",
                "to": "2026-01-01T00:30Z",
                "intensity": {"forecast": 102, "actual": 110},
            },
            {
                "from": "2026-01-01T00:30Z",
                "to": "2026-01-01T01:00Z",
                "intensity": {"forecast": 105, "actual": None},
            },
        ]
    }
