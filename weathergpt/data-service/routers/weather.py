from fastapi import APIRouter, HTTPException, Query
from typing import Optional
import httpx
import os

router = APIRouter()

OWM_KEY = os.getenv("OPENWEATHER_API_KEY", "")
OWM_BASE = "https://api.openweathermap.org/data/2.5"
GEO_BASE = "https://api.openweathermap.org/geo/1.0"

async def resolve_location(location: str = None, lat: float = None, lon: float = None):
    """Resolve location name to lat/lon."""
    if lat and lon:
        return float(lat), float(lon)
    if location:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{GEO_BASE}/direct", params={
                "q": location, "limit": 1, "appid": OWM_KEY
            })
            data = resp.json()
            if data:
                return data[0]["lat"], data[0]["lon"]
    return 19.0760, 72.8777  # Default Mumbai

@router.get("/current")
async def current_weather(
    location: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None
):
    try:
        rlat, rlon = await resolve_location(location, lat, lon)
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{OWM_BASE}/weather", params={
                "lat": rlat, "lon": rlon,
                "appid": OWM_KEY, "units": "metric"
            })
            data = resp.json()

        if data.get("cod") != 200:
            raise HTTPException(status_code=404, detail="Location not found")

        return {
            "location": data.get("name"),
            "lat": rlat, "lon": rlon,
            "temperature": data["main"]["temp"],
            "feels_like": data["main"]["feels_like"],
            "humidity": data["main"]["humidity"],
            "pressure": data["main"]["pressure"],
            "wind_speed": data["wind"]["speed"],
            "wind_deg": data["wind"].get("deg"),
            "description": data["weather"][0]["description"],
            "icon": data["weather"][0]["icon"],
            "visibility": data.get("visibility"),
            "rainfall_1h": data.get("rain", {}).get("1h", 0),
            "source": "OpenWeatherMap",
            "timestamp": data["dt"]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/forecast")
async def weather_forecast(
    location: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    days: Optional[int] = 7
):
    try:
        rlat, rlon = await resolve_location(location, lat, lon)
        async with httpx.AsyncClient() as client:
            # Use Open-Meteo (free, no key needed) for multi-day forecast
            resp = await client.get("https://api.open-meteo.com/v1/forecast", params={
                "latitude": rlat, "longitude": rlon,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max,weathercode",
                "hourly": "temperature_2m,precipitation,windspeed_10m,relativehumidity_2m",
                "timezone": "Asia/Kolkata",
                "forecast_days": min(days, 16)
            })
            data = resp.json()

        daily = data.get("daily", {})
        forecast_days = []
        times = daily.get("time", [])
        for i, date in enumerate(times):
            forecast_days.append({
                "date": date,
                "temp_max": daily["temperature_2m_max"][i],
                "temp_min": daily["temperature_2m_min"][i],
                "precipitation": daily["precipitation_sum"][i],
                "wind_max": daily["windspeed_10m_max"][i],
                "weather_code": daily["weathercode"][i]
            })

        return {
            "location": location or f"{rlat},{rlon}",
            "lat": rlat, "lon": rlon,
            "forecast": forecast_days,
            "source": "Open-Meteo",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
