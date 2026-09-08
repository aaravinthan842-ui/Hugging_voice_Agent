import os
import logging
from groq import AsyncGroq

logger = logging.getLogger(__name__)

_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))


async def transcribe_audio(audio_bytes: bytes, filename: str = "recording.webm") -> str:
    """
    Transcribe audio bytes to text using Groq's hosted Whisper model.
    Raises RuntimeError on failure so callers can handle it explicitly.
    """
    try:
        transcription = await _client.audio.transcriptions.create(
            file=(filename, audio_bytes),
            model="whisper-large-v3",
            language="en",
        )
        text = transcription.text.strip()
        logger.info("STT success | chars=%d", len(text))
        return text
    except Exception as e:
        logger.exception("STT failed")
        raise RuntimeError(f"Transcription failed: {e}") from e