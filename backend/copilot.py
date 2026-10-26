"""AI Scalp Copilot — gated (COPILOT_ENABLED, default false), login-required, per-user scoped.

Education / structured practice only. Never executes or routes orders.
"""
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

DISCLAIMER = (
    "Futures trading involves substantial risk of loss and is not suitable for all investors. "
    "This is education and structured practice, not financial advice. "
    "Past performance is not indicative of future results."
)
SECTIONS = ("Session", "Location", "Trigger", "Risk", "Review")
GPT_MODELS = {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini"}

METHOD_PROMPT = (
    "You are Scalp Copilot for MNQ Scalp Stacks, an education and structured-practice platform. "
    "All desk data is PAPER/SIM/TEST — never call it live, and never present it as performance proof.\n"
    "Approved method ONLY: EMA21 is the spine (trend/side filter); VWAP is location (above = long-only "
    "context, below = short-only context); the trigger requires 1m and 5m alignment, read top-down "
    "15m structure -> 5m bias -> 1m entry. Do NOT use an EMA9 cross or RSI cross as a trigger.\n"
    "Always answer in exactly these five labeled sections, in order, plain text, no markdown:\n"
    "Session: ...\nLocation: ...\nTrigger: ...\nRisk: ...\nReview: ...\n"
    "Never guarantee profits, never give personalized financial advice, and refuse any request to "
    "place, route, modify, or cancel orders — you cannot execute trades. Keep it under 160 words. "
    "Do not write a disclaimer yourself; the platform appends it."
)

_EXEC_RE = re.compile(
    r"\b(place|execute|submit|send|route|enter|open|close|flatten|cancel|modify)\b.{0,40}\b(order|trade|position|contract|long|short)s?\b"
    r"|\b(buy|sell)\s+(\d+|one|a|an|some|mnq|nq|contracts?)\b"
    r"|\b(go|get)\s+(long|short)\b(?!.*\?)",
    re.IGNORECASE,
)

REFUSAL_BODY = (
    "Session: I can't place, route, modify, or cancel orders — Scalp Copilot is education only and has no execution access.\n"
    "Location: Review where price sits versus VWAP and the EMA21 spine on your own chart.\n"
    "Trigger: Confirm 15m structure, 5m bias, then 1m alignment before you act in your own platform.\n"
    "Risk: Define the stop and size first; respect the $100 daily loss lockout.\n"
    "Review: Log the setup in your journal after the session, win or lose."
)


def copilot_enabled() -> bool:
    return os.environ.get("COPILOT_ENABLED", "false").strip().lower() == "true"


def is_execution_request(text: str) -> bool:
    return bool(_EXEC_RE.search(text or ""))


def with_disclaimer(text: str) -> str:
    text = (text or "").rstrip()
    if text.endswith(DISCLAIMER):
        return text
    return f"{text}\n\n{DISCLAIMER}"


class CopilotBody(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=2000)
    provider: str = "gpt"
    model: str = "gpt-5.4"


# provider signature: (provider, model, system, message, session_id) -> async iterator of str chunks
Provider = Callable[[str, str, str, str, str], AsyncIterator[str]]


def build_copilot_router(
    db: Any,
    get_current_user: Callable[[Request, Any], Awaitable[Dict[str, Any]]],
    context_fn: Callable[[], Awaitable[str]],
    stream_provider: Provider,
    logger: Any = None,
) -> APIRouter:
    router = APIRouter(prefix="/copilot", tags=["ai"])

    def _gate() -> None:
        if not copilot_enabled():
            raise HTTPException(status_code=404, detail="Not Found")

    @router.get("/status")
    async def copilot_status() -> Dict[str, Any]:
        """Public. Booleans only — never key values, prefixes, or lengths."""
        return {
            "enabled": copilot_enabled(),
            "providers": {
                "gpt": bool(os.environ.get("EMERGENT_LLM_KEY")),
                "grok": bool(os.environ.get("XAI_API_KEY")),
            },
        }

    async def _owned_session(session_id: str, user_id: str) -> None:
        sess = await db.copilot_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if sess is None:
            await db.copilot_sessions.insert_one({
                "session_id": session_id, "user_id": user_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        elif sess.get("user_id") != user_id:
            raise HTTPException(status_code=403, detail="Forbidden")

    @router.post("/chat")
    async def copilot_chat(body: CopilotBody, request: Request):
        _gate()
        user = await get_current_user(request, db)
        user_id = user["user_id"]
        msg = body.message.strip()
        if not msg:
            raise HTTPException(status_code=400, detail="Empty message")
        await _owned_session(body.session_id, user_id)
        now = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731
        await db.copilot_messages.insert_one({
            "session_id": body.session_id, "user_id": user_id, "role": "user", "content": msg, "created_at": now(),
        })

        if is_execution_request(msg):
            text = with_disclaimer(REFUSAL_BODY)
            await db.copilot_messages.insert_one({
                "session_id": body.session_id, "user_id": user_id, "role": "assistant",
                "content": text, "provider": "refusal", "created_at": now(),
            })

            async def refuse():
                yield text
            return StreamingResponse(refuse(), media_type="text/plain", headers={"Cache-Control": "no-cache"})

        history = await db.copilot_messages.find(
            {"session_id": body.session_id, "user_id": user_id}, {"_id": 0, "role": 1, "content": 1}
        ).sort("created_at", 1).to_list(40)
        transcript = "\n".join(f"{m['role'].upper()}: {m['content'][:600]}" for m in history[-12:]) or "(new conversation)"
        context = await context_fn()
        system = f"{METHOD_PROMPT}\n\nPAPER/SIM DESK CONTEXT (not live, not performance proof):\n{context}\n\nCONVERSATION SO FAR:\n{transcript}"
        provider = "grok" if body.provider.lower() == "grok" and os.environ.get("XAI_API_KEY") else "gpt"
        model = "grok-4.6" if provider == "grok" else (body.model if body.model in GPT_MODELS else "gpt-5.4")

        async def gen():
            parts: List[str] = []
            try:
                async for chunk in stream_provider(provider, model, system, msg, body.session_id):
                    if chunk:
                        parts.append(chunk)
                        yield chunk
            except Exception as e:  # never leak provider errors/keys
                if logger:
                    logger.error(f"Copilot stream error ({provider}): {type(e).__name__}")
                parts.append("\n[Copilot hit an error — try again.]")
                yield parts[-1]
            tail = "\n\n" + DISCLAIMER
            yield tail
            await db.copilot_messages.insert_one({
                "session_id": body.session_id, "user_id": user_id, "role": "assistant",
                "content": "".join(parts) + tail, "provider": provider, "model": model, "created_at": now(),
            })

        return StreamingResponse(gen(), media_type="text/plain",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @router.get("/history/{session_id}")
    async def copilot_history(session_id: str, request: Request):
        _gate()
        user = await get_current_user(request, db)
        sess = await db.copilot_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if sess and sess.get("user_id") != user["user_id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        return await db.copilot_messages.find(
            {"session_id": session_id, "user_id": user["user_id"]},
            {"_id": 0, "role": 1, "content": 1, "created_at": 1},
        ).sort("created_at", 1).to_list(60)

    return router


def new_session_id() -> str:
    return uuid.uuid4().hex
