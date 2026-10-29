"""
Proxy active alerts from the backend MongoDB via the Node API,
or return empty list if backend is unreachable.
"""
from fastapi import APIRouter
import httpx
import os

router = APIRouter()
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:4000")


@router.get("/alerts")
async def get_alerts():
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{BACKEND_URL}/api/alerts")
            return r.json() if r.status_code == 200 else []
    except Exception:
        return []
