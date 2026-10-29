from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(dotenv_path='../.env')

from routers import weather, climate, geocode, alerts

app = FastAPI(title="WeatherGPT Data Service")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(weather.router, prefix="/weather")
app.include_router(climate.router, prefix="/climate")
app.include_router(geocode.router, prefix="/geocode")
app.include_router(alerts.router)

@app.get("/health")
def health():
    return {"status": "ok"}
