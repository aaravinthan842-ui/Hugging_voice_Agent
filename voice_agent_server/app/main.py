import logging
import time
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse

from app.services.gemini import transcribe_audio
from app.services.conversation import get_ai_response, clear_session
from app.services.tts import text_to_speech

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("voice_agent")

app = FastAPI(title="Voice Agent Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"message": "LangChain Voice AI is Running!"}


@app.post("/voice-chat")
async def voice_chat(
    audio: UploadFile = File(...),
    session_id: str = Form(default="default"),
):
    total_start = time.perf_counter()

    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            return JSONResponse(
                status_code=400,
                content={"error": "Empty audio file received."},
            )
    except Exception as e:
        logger.exception("Failed to read uploaded audio")
        return JSONResponse(status_code=400, content={"error": f"Could not read audio: {e}"})

    # --- STT ---
    t0 = time.perf_counter()
    try:
        user_text = await transcribe_audio(audio_bytes, filename=audio.filename or "recording.webm")
    except RuntimeError as e:
        logger.error("STT stage failed: %s", e)
        return JSONResponse(status_code=502, content={"error": str(e)})
    stt_time = time.perf_counter() - t0

    if not user_text:
        return JSONResponse(status_code=400, content={"error": "Could not understand audio (empty transcript)."})

    # --- LLM ---
    t0 = time.perf_counter()
    try:
        ai_reply = await get_ai_response(user_text, session_id)
    except (RuntimeError, ValueError) as e:
        logger.error("LLM stage failed: %s", e)
        return JSONResponse(status_code=502, content={"error": str(e)})
    llm_time = time.perf_counter() - t0

    # --- TTS ---
    # text_to_speech returns (audio_bytes, audio_format) since the primary
    # provider (Orpheus, "wav") and the fallback (gTTS, "mp3") differ.
    t0 = time.perf_counter()
    try:
        audio_response, audio_format = await text_to_speech(ai_reply)
    except Exception as e:
        logger.exception("TTS stage failed")
        return JSONResponse(status_code=502, content={"error": f"TTS failed: {e}"})
    tts_time = time.perf_counter() - t0

    total_time = time.perf_counter() - total_start
    logger.info(
        "voice-chat done | session=%s | stt=%.2fs llm=%.2fs tts=%.2fs total=%.2fs | format=%s",
        session_id, stt_time, llm_time, tts_time, total_time, audio_format,
    )

    media_type = "audio/wav" if audio_format == "wav" else "audio/mpeg"

    return Response(
        content=audio_response,
        media_type=media_type,
        headers={
            "X-Transcript": urllib.parse.quote(user_text),
            "X-AI-Reply": urllib.parse.quote(ai_reply),
            "X-Audio-Format": audio_format,
            "X-Stt-Time": f"{stt_time:.2f}",
            "X-Llm-Time": f"{llm_time:.2f}",
            "X-Tts-Time": f"{tts_time:.2f}",
            "X-Total-Time": f"{total_time:.2f}",
            "Access-Control-Expose-Headers":
                "X-Transcript, X-AI-Reply, X-Audio-Format, X-Stt-Time, X-Llm-Time, X-Tts-Time, X-Total-Time",
        },
    )


@app.post("/clear-session")
def clear_chat_session(session_id: str = "default"):
    clear_session(session_id)
    return JSONResponse({"message": f"Session '{session_id}' cleared!"})

@app.get("/health")
def health():
    return {"status": "voice agnet Running Successfully"}