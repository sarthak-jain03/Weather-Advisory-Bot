from __future__ import annotations

import httpx
from datetime import datetime, timezone, timedelta

GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
AQI_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

IST = timedelta(hours=5, minutes=30)

CURRENT_FIELDS = [
    "temperature_2m",
    "wind_speed_10m",
    "wind_gusts_10m",
    "precipitation",
    "relative_humidity_2m",
    "uv_index",
]

HOURLY_FIELDS = [
    "precipitation_probability",
    "visibility",
]


async def geocode_city(city_name: str) -> tuple[float, float] | None:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(GEOCODE_URL, params={"name": city_name, "count": 5})
        resp.raise_for_status()
        data = resp.json()

    results = data.get("results")
    if not results:
        return None

    for r in results:
        if r.get("country_code", "").upper() == "IN":
            return r["latitude"], r["longitude"]
    return results[0]["latitude"], results[0]["longitude"]


async def fetch_weather(latitude: float, longitude: float) -> dict:
    async with httpx.AsyncClient(timeout=10.0) as client:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(CURRENT_FIELDS),
            "hourly": ",".join(HOURLY_FIELDS),
            "timezone": "auto",
            "forecast_days": 1,
        }
        resp = await client.get(FORECAST_URL, params=params)
        resp.raise_for_status()
        forecast = resp.json()

        aqi_value = None
        try:
            aqi_resp = await client.get(
                AQI_URL,
                params={
                    "latitude": latitude,
                    "longitude": longitude,
                    "current": "us_aqi",
                },
            )
            aqi_resp.raise_for_status()
            aqi_data = aqi_resp.json()
            aqi_value = aqi_data.get("current", {}).get("us_aqi")
        except Exception:
            pass

    current = forecast.get("current", {})
    hourly = forecast.get("hourly", {})
    hourly_times = hourly.get("time", [])

    now_str = current.get("time", "")
    current_hour_idx = 0
    if now_str and hourly_times:
        try:
            current_dt = datetime.fromisoformat(now_str)
            for i, t in enumerate(hourly_times):
                if datetime.fromisoformat(t).hour == current_dt.hour:
                    current_hour_idx = i
                    break
        except Exception:
            pass

    result = {
        "temperature_2m": current.get("temperature_2m"),
        "wind_speed_10m": current.get("wind_speed_10m"),
        "wind_gusts_10m": current.get("wind_gusts_10m"),
        "precipitation": current.get("precipitation"),
        "relative_humidity_2m": current.get("relative_humidity_2m"),
        "uv_index": current.get("uv_index"),
        "us_aqi": aqi_value,
        "raw_response": forecast,
    }

    for field in HOURLY_FIELDS:
        values = hourly.get(field, [])
        if values and current_hour_idx < len(values):
            result[field] = values[current_hour_idx]
        else:
            result[field] = None

    try:
        tz_offset = forecast.get("utc_offset_seconds", 19800)
        utc_now = datetime.now(timezone.utc)
        local_now = utc_now + timedelta(seconds=tz_offset)
        result["current_hour"] = local_now.hour
    except Exception:
        result["current_hour"] = datetime.now().hour

    return result
