import os
import io
import asyncio
import logging
from typing import Tuple

from groq import AsyncGroq

logger = logging.getLogger(__name__)

_client = AsyncGroq(api_key=os.getenv("GROQ_API_KEY"))

TTS_MODEL = "canopylabs/orpheus-v1-english"
DEFAULT_VOICE = "troy"
ORPHEUS_MAX_CHARS = 200

ORPHEUS_TIMEOUT_S = 10
GTTS_TIMEOUT_S = 8


async def text_to_speech(text: str, voice: str = DEFAULT_VOICE) -> Tuple[bytes, str]:
    """
    Convert text to speech using Groq's Orpheus TTS model.
    Returns (audio_bytes, audio_format) where audio_format is "wav" or "mp3".
    Falls back to gTTS (mp3) if the Groq call fails, so the endpoint never
    hard-fails just because of a TTS provider hiccup.
    """
    
    safe_text = text[:ORPHEUS_MAX_CHARS]

    try:
        response = await asyncio.wait_for(
            _client.audio.speech.create(
                model=TTS_MODEL,
                voice=voice,
                input=safe_text,
                response_format="wav",  # Orpheus currently only supports "wav"
            ),
            timeout=ORPHEUS_TIMEOUT_S,
        )
        audio_bytes = response.read()
        logger.info("TTS (Groq Orpheus) success | chars=%d", len(safe_text))
        return audio_bytes, "wav"
    except asyncio.TimeoutError:
        logger.warning("Groq Orpheus TTS timed out after %ss, falling back to gTTS", ORPHEUS_TIMEOUT_S)
    except Exception as e:
        if "model_terms_required" in str(e):
            logger.error(
                "Orpheus TTS blocked: terms not accepted for this Groq account. "
                "Accept at https://console.groq.com/playground?model=canopylabs%%2Forpheus-v1-english"
            )
        else:
            logger.warning("Groq Orpheus TTS failed, falling back to gTTS: %s", e)

    try:
        audio_bytes = await asyncio.wait_for(
            asyncio.to_thread(_fallback_gtts, text),
            timeout=GTTS_TIMEOUT_S,
        )
        return audio_bytes, "mp3"
    except asyncio.TimeoutError:
        raise RuntimeError(
            "Both Orpheus and gTTS failed/timed out — check Groq account terms "
            "acceptance and network access to translate.google.com"
        )


def _fallback_gtts(text: str, lang: str = "en") -> bytes:
    from gtts import gTTS

    tts = gTTS(text=text, lang=lang, slow=False)
    mp3_buffer = io.BytesIO()
    tts.write_to_fp(mp3_buffer)
    mp3_buffer.seek(0)
    return mp3_buffer.read()