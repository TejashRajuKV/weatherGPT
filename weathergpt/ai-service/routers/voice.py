from fastapi import APIRouter

router = APIRouter(prefix="/voice")

# Voice is handled entirely in the browser via Web Speech API.
# These endpoints are stubs kept for API compatibility.

@router.post("/transcribe")
async def transcribe():
    return {"message": "Use browser Web Speech API for transcription."}

@router.post("/speak")
async def speak():
    return {"message": "Use browser SpeechSynthesis API for text-to-speech."}
