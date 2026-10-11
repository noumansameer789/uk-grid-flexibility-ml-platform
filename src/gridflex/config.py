import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("GRIDFLEX_DATA_DIR", "data"))
    model_dir: Path = Path(os.getenv("GRIDFLEX_MODEL_DIR", "models/production"))
    carbon_url: str = "https://api.carbonintensity.org.uk"
    weather_url: str = "https://api.open-meteo.com/v1/forecast"
    archive_url: str = "https://archive-api.open-meteo.com/v1/archive"
    timeout: float = 15.0
    cache_seconds: int = 600
    failure_cache_seconds: int = 30
    max_body_bytes: int = 16384
    api_requests_per_minute: int = 120


LOCATIONS = {
    "London": (51.5074, -0.1278),
    "Manchester": (53.4808, -2.2426),
    "Edinburgh": (55.9533, -3.1883),
}
WEATHER_VARIABLES = ["temperature_2m", "wind_speed_10m", "cloud_cover", "shortwave_radiation"]
