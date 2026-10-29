from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv(dotenv_path='../.env')

from routers import chat, voice

app = FastAPI(title="WeatherGPT AI Service (Rule-based NLP)")

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

app.include_router(chat.router)
app.include_router(voice.router)

@app.get("/health")
def health():
    return {"status": "ok", "mode": "rule-based-nlp"}
