"""Current conditions and short-range forecast from Open-Meteo.

Forecast values are point-based weather-model outputs, not field observations.
"""
from __future__ import annotations

import httpx


FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
CURRENT_VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "apparent_temperature",
    "precipitation",
    "wind_speed_10m",
    "wind_gusts_10m",
    "weather_code",
]
DAILY_VARIABLES = [
    "temperature_2m_max",
    "temperature_2m_min",
    "precipitation_sum",
    "precipitation_probability_max",
    "wind_speed_10m_max",
    "et0_fao_evapotranspiration",
]


async def fetch_weather_forecast(lat: float, lon: float, forecast_days: int = 16) -> dict:
    if not 1 <= forecast_days <= 16:
        raise ValueError("forecast_days 1–16 oralig‘ida bo‘lishi kerak")

    params = {
        "latitude": f"{lat:.5f}",
        "longitude": f"{lon:.5f}",
        "current": ",".join(CURRENT_VARIABLES),
        "daily": ",".join(DAILY_VARIABLES),
        "forecast_days": forecast_days,
        "timezone": "auto",
        "temperature_unit": "celsius",
        "wind_speed_unit": "kmh",
        "precipitation_unit": "mm",
    }

    async with httpx.AsyncClient(timeout=45, follow_redirects=True) as client:
        response = await client.get(
            FORECAST_URL,
            params=params,
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json()

    current = payload.get("current") or {}
    daily = payload.get("daily") or {}
    dates = daily.get("time") or []

    def at(key: str, index: int):
        values = daily.get(key) or []
        return values[index] if index < len(values) else None

    rows = []
    for i, day in enumerate(dates):
        rows.append({
            "date": day,
            "temperature_max_c": at("temperature_2m_max", i),
            "temperature_min_c": at("temperature_2m_min", i),
            "precipitation_sum_mm": at("precipitation_sum", i),
            "precipitation_probability_max_pct": at("precipitation_probability_max", i),
            "wind_speed_max_kmh": at("wind_speed_10m_max", i),
            "et0_fao_mm": at("et0_fao_evapotranspiration", i),
        })

    return {
        "status": "AVAILABLE" if current or rows else "NO_DATA",
        "source": "Open-Meteo Forecast API",
        "timezone": payload.get("timezone"),
        "elevation_m": payload.get("elevation"),
        "current": current,
        "daily": rows,
        "forecast_days_returned": len(rows),
        "units": {
            "temperature": "°C",
            "precipitation": "mm",
            "wind_speed": "km/h",
            "reference_evapotranspiration": "mm/day",
        },
        "attribution": "Weather-model forecast from Open-Meteo; not a measurement from the selected field.",
    }
