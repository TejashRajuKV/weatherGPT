from fastapi import APIRouter
import httpx
import os

router = APIRouter()
OWM_KEY = os.getenv("OPENWEATHER_API_KEY", "")

@router.get("/search")
async def geocode_search(q: str):
    """Resolve location name to lat/lon."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.openweathermap.org/geo/1.0/direct",
                params={"q": q, "limit": 5, "appid": OWM_KEY}
            )
            return resp.json()
    except Exception as e:
        return {"error": str(e)}
