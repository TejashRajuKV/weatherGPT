from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import httpx
import os

from services.nlp import parse_query, generate_response

router = APIRouter()

DATA_SERVICE_URL = os.getenv("DATA_SERVICE_URL", "http://localhost:8002")


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    query: str
    location: Optional[str] = None
    language: Optional[str] = "en"
    history: Optional[List[Message]] = []
    context: Optional[dict] = None   # conversation context for follow-ups


@router.post("/chat")
async def chat(req: ChatRequest):
    try:
        # Step 1: Full NLP pipeline — normalize, detect lang, parse intent/location/time
        parsed = parse_query(req.query, context=req.context or {})

        # Override location from UI field if NLP found nothing
        if req.location and not parsed.get("location"):
            parsed["location"] = req.location

        location   = parsed.get("location") or "Mumbai"
        intent     = parsed.get("intent", "current")
        fetch_list = parsed.get("fetch", ["current"])  # what data is needed

        # Step 2: Fetch exactly what the intent needs (in parallel where possible)
        weather_data = {}
        async with httpx.AsyncClient(timeout=10.0) as client:

            if "current" in fetch_list:
                try:
                    r = await client.get(
                        f"{DATA_SERVICE_URL}/weather/current",
                        params={"location": location}
                    )
                    weather_data["current"] = r.json() if r.status_code == 200 else {}
                except Exception:
                    weather_data["current"] = {}

            if "forecast" in fetch_list:
                # Determine days needed from time range
                time_range = parsed.get("time_range", "today")
                days = 7
                if "tomorrow" in time_range:    days = 2
                elif time_range == "today" or time_range == "tonight": days = 1
                elif time_range == "day_after_tomorrow": days = 3
                elif "next_" in time_range and "_days" in time_range:
                    try: days = int(time_range.split("_")[1])
                    except Exception: days = 7
                elif "in_" in time_range and "_days" in time_range:
                    try: days = int(time_range.split("_")[1]) + 1
                    except Exception: days = 7
                try:
                    r = await client.get(
                        f"{DATA_SERVICE_URL}/weather/forecast",
                        params={"location": location, "days": min(days, 16)}
                    )
                    weather_data["forecast"] = r.json() if r.status_code == 200 else {}
                except Exception:
                    weather_data["forecast"] = {}

            if "alerts" in fetch_list:
                try:
                    r = await client.get(f"{DATA_SERVICE_URL}/alerts")
                    weather_data["alerts"] = r.json() if r.status_code == 200 else []
                except Exception:
                    weather_data["alerts"] = []

            if "climate" in fetch_list:
                try:
                    r = await client.get(
                        f"{DATA_SERVICE_URL}/climate/history",
                        params={"location": location}
                    )
                    weather_data["climate"] = r.json() if r.status_code == 200 else {}
                except Exception:
                    weather_data["climate"] = {}

        # Step 3: Generate rule-based response
        response_text = generate_response(intent, parsed, weather_data)

        return {
            "response":      response_text,
            "intent":        intent,
            "intent_source": parsed.get("intent_source", "rules"),
            "location":      location,
            "language":      parsed.get("language", "en"),
            "time_range":    parsed.get("time_range", "today"),
            "context":       parsed,    # return for follow-up queries
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
