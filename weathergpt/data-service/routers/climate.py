from fastapi import APIRouter, Query
from typing import Optional
import httpx

router = APIRouter()

@router.get("/history")
async def climate_history(
    location: Optional[str] = None,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to")
):
    """Fetch historical climate data using Open-Meteo Archive API."""
    try:
        # Default: last 30 days if no range given
        from datetime import date, timedelta
        end = to_date or str(date.today())
        start = from_date or str(date.today() - timedelta(days=30))

        # Resolve coords if needed
        rlat = lat or 19.0760
        rlon = lon or 72.8777

        if location and not (lat and lon):
            async with httpx.AsyncClient() as client:
                geo = await client.get(
                    "https://api.openweathermap.org/geo/1.0/direct",
                    params={"q": location, "limit": 1, "appid": "placeholder"}
                )
                gdata = geo.json()
                if gdata:
                    rlat, rlon = gdata[0]["lat"], gdata[0]["lon"]

        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get("https://archive-api.open-meteo.com/v1/archive", params={
                "latitude": rlat, "longitude": rlon,
                "start_date": start, "end_date": end,
                "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,windspeed_10m_max",
                "timezone": "Asia/Kolkata"
            })
            data = resp.json()

        daily = data.get("daily", {})
        records = []
        for i, d in enumerate(daily.get("time", [])):
            records.append({
                "date": d,
                "temp_max": daily["temperature_2m_max"][i],
                "temp_min": daily["temperature_2m_min"][i],
                "precipitation": daily["precipitation_sum"][i],
                "wind_max": daily["windspeed_10m_max"][i]
            })

        return {"location": location, "from": start, "to": end, "records": records, "source": "Open-Meteo Archive"}
    except Exception as e:
        return {"error": str(e), "records": []}
