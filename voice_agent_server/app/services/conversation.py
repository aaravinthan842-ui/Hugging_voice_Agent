import os
import logging
import time
from threading import Lock

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

logger = logging.getLogger(__name__)

_sessions: dict[str, list] = {}
_sessions_lock = Lock()

MAX_HISTORY_MESSAGES = 20  # keep last N messages (user+ai pairs)

PROMPT = ChatPromptTemplate.from_messages([
    ("system",
     "You are a friendly AI voice assistant having a warm natural conversation. "
     "Reply in 1-2 short sentences only. "
     "No bullet points, no markdown — plain spoken words only. "
     "This will be converted to speech. "
     "Remember the full conversation context."),
    MessagesPlaceholder(variable_name="history"),
    ("human", "{input}"),
])

# --- Singleton LLM + chain (built once, reused across requests) ---
_llm = None
_chain = None
_llm_lock = Lock()


def _get_chain():
    global _llm, _chain
    if _chain is None:
        with _llm_lock:
            if _chain is None:  # double-checked locking
                api_key = os.getenv("GROQ_API_KEY")
                if not api_key:
                    raise RuntimeError("GROQ_API_KEY is not set")
                # llama-3.1-8b-instant is deprecated by Groq, shutdown 08/16/2026.
                # Recommended replacement: openai/gpt-oss-20b (same speed tier).
                # https://console.groq.com/docs/deprecations
                _llm = ChatGroq(
                    model="openai/gpt-oss-20b",
                    api_key=api_key,
                    temperature=0.8,
                )
                _chain = PROMPT | _llm
                logger.info("ChatGroq client initialized (singleton)")
    return _chain


def _get_history(session_id: str) -> list:
    with _sessions_lock:
        return _sessions.setdefault(session_id, [])


async def get_ai_response(user_text: str, session_id: str = "default") -> str:
    """
    Get an AI reply for user_text, maintaining per-session history.
    Raises RuntimeError on failure.
    """
    if not user_text or not user_text.strip():
        raise ValueError("user_text is empty")

    history = _get_history(session_id)
    chain = _get_chain()

    start = time.perf_counter()
    try:
        response = await chain.ainvoke({"history": history, "input": user_text})
    except Exception as e:
        logger.exception("LLM call failed")
        raise RuntimeError(f"AI response failed: {e}") from e
    elapsed = time.perf_counter() - start
    logger.info("LLM response in %.2fs | session=%s", elapsed, session_id)

    reply = response.content.strip()

    with _sessions_lock:
        history.append(HumanMessage(content=user_text))
        history.append(AIMessage(content=reply))
        if len(history) > MAX_HISTORY_MESSAGES:
            _sessions[session_id] = history[-MAX_HISTORY_MESSAGES:]

    return reply


def clear_session(session_id: str = "default") -> None:
    with _sessions_lock:
        _sessions.pop(session_id, None)
    logger.info("Session cleared | session=%s", session_id)