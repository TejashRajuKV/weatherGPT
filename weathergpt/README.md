# WeatherGPT

AI-powered conversational weather platform.

## Prerequisites
- Node.js 18+
- Python 3.10+
- MongoDB running locally on port 27017

## Setup

### 1. Environment variables
Fill in your API keys in `.env`:
```
OPENWEATHER_API_KEY=...   ← free at openweathermap.org
JWT_SECRET=...            ← any random string, e.g. "mysecret123"
```
No AI/LLM API key needed. The AI layer uses a built-in rule-based NLP engine.

### 2. Backend (Node.js)
```bash
cd backend
npm install
npm run dev
```
Runs on http://localhost:4000

### 3. AI Service (Python)
```bash
cd ai-service
pip install -r requirements.txt
uvicorn main:app --port 8001 --reload
```

### 4. Data Service (Python)
```bash
cd data-service
pip install -r requirements.txt
uvicorn main:app --port 8002 --reload
```

### 5. Frontend (React)
```bash
cd frontend
npm install
npm run dev
```
Opens on http://localhost:3000

## Architecture
- **Frontend** — React + Vite on :3000
- **Backend** — Node.js Express API gateway on :4000
- **AI Service** — FastAPI LLM orchestration on :8001
- **Data Service** — FastAPI weather data on :8002
- **MongoDB** — localhost:27017
