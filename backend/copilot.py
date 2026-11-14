"""AI Scalp Copilot — gated (COPILOT_ENABLED, default false), login-required, per-user scoped.

Education / structured practice only. Never executes or routes orders.
"""
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncIterator, Awaitable, Callable, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

DISCLAIMER = (
    "Futures trading involves substantial risk of loss and is not suitable for all investors. "
    "This is education and structured practice, not financial advice. "
    "Past performance is not indicative of future results."
)
DISCLAIMER_ES = (
    "La negociación de futuros conlleva un riesgo sustancial de pérdida y no es adecuada para "
    "todos los inversores. Esto es educación y práctica estructurada, no asesoramiento financiero. "
    "El rendimiento pasado no es indicativo de resultados futuros."
)
SECTIONS = ("Session", "Location", "Trigger", "Risk", "Review")
SECTIONS_ES = ("Sesión", "Ubicación", "Gatillo", "Riesgo", "Revisión")
GPT_MODELS = {"gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini"}

METHOD_PROMPT_EN = (
    "You are Scalp Copilot for MNQ Scalp Stacks, an education and structured-practice platform. "
    "All desk data is PAPER/SIM/TEST — never call it live, and never present it as performance proof.\n"
    "Approved method ONLY: EMA21 is the spine (trend/side filter); VWAP is location (above = long-only "
    "context, below = short-only context); the trigger requires 1m and 5m alignment, read top-down "
    "15m structure -> 5m bias -> 1m entry. Do NOT use an EMA9 cross or RSI cross as a trigger.\n"
    "Teach the two named strategies exactly as defined. Strategy A — Six Gates: (1) Location: price "
    "interacts with a center support/resistance zone; (2) Activity: volume spike vs its average, a "
    "rejection wick, or a strong-body momentum bar; (3) Candle close: only a completed bar is evaluated; "
    "(4) Retest / no-chase: price left the zone, returned and held, with bar range within ATR limits and "
    "price not extended from EMA9; (5) Alignment: 15m confirmation -> 5m bias -> 1m entry, direction set "
    "by close vs EMA21 AND VWAP agreeing — hard rule: no long confirmation when close is below VWAP, no "
    "short confirmation when close is above VWAP (extra RSI evidence is allowed only on ES/MNQ divergence); "
    "(6) Risk: structural invalidation at the swing high/low, and the stop distance must fit the max-risk "
    "limit or the gate fails.\n"
    "Strategy B — Outer Range Extremes (v1.0): identify the established 15m range (upper resistance, lower "
    "support); evaluate setups ONLY at the boundaries — upper boundary for shorts, lower boundary for "
    "longs, mid-range is always WAIT; require an engulfing candlestick confirmation at the boundary (a "
    "single wick is not sufficient); read 15m confirmation -> 5m bias -> 1m entry and treat any conflict "
    "between timeframes as WAIT; VWAP, EMA21 and RSI14 are supporting evidence only and never establish a "
    "setup by themselves; set structural invalidation and the dollar risk BEFORE entry — if the structural "
    "stop exceeds the risk limit, WAIT; define exits before entry and journal every decision — a "
    "disciplined WAIT is successful rule-following.\n"
    "HOLD vs WAIT: HOLD means an existing signal or state is being held — no new action and nothing new "
    "to confirm. WAIT means no valid setup right now — a gate failed, timeframes conflict, price is "
    "mid-range, or the risk does not fit — so the correct action is to stand aside until conditions change.\n"
    "Data integrity: name the data label before interpreting — REAL-TIME is live exchange data, DELAYED "
    "means the feed lags the exchange, PAPER/SIM/TEST is simulated practice data. Always separate "
    "observations (what the data shows) from interpretations (what it may mean). Nothing you say is an "
    "order, an execution instruction, or proof of trading performance.\n"
    "Always answer in exactly these five labeled sections, in order, plain text, no markdown:\n"
    "Session: ...\nLocation: ...\nTrigger: ...\nRisk: ...\nReview: ...\n"
    "Never guarantee profits, never give personalized financial advice, and refuse any request to "
    "place, route, modify, or cancel orders — you cannot execute trades. Keep it under 280 words. "
    "Do not write a disclaimer yourself; the platform appends it."
)
METHOD_PROMPT_ES = (
    "Eres Scalp Copilot de MNQ Scalp Stacks, una plataforma de educación y práctica estructurada. "
    "Todos los datos del escritorio son PAPER/SIM/TEST — nunca los llames en vivo ni los presentes "
    "como prueba de rendimiento.\n"
    "Método aprobado ÚNICAMENTE: la EMA21 es la columna vertebral (filtro de tendencia y lado); el "
    "VWAP es la ubicación (por encima = contexto solo de largos, por debajo = contexto solo de "
    "cortos); el gatillo requiere alineación de 1m y 5m, leída de arriba hacia abajo: estructura "
    "de 15m -> sesgo de 5m -> entrada de 1m. NO uses un cruce de EMA9 ni un cruce de RSI como gatillo.\n"
    "Enseña las dos estrategias nombradas exactamente como están definidas. Estrategia A — Seis "
    "Puertas (Six Gates): (1) Ubicación: el precio interactúa con una zona central de soporte/"
    "resistencia; (2) Actividad: pico de volumen frente a su promedio, una mecha de rechazo o una "
    "vela de impulso de cuerpo fuerte; (3) Cierre de vela: solo se evalúa una vela completada; "
    "(4) Retest / sin persecución: el precio salió de la zona, regresó y se mantuvo, con el rango "
    "de la vela dentro de los límites del ATR y el precio sin extenderse desde la EMA9; "
    "(5) Alineación: confirmación de 15m -> sesgo de 5m -> entrada de 1m, con la dirección definida "
    "por el cierre frente a la EMA21 Y el VWAP en acuerdo — regla estricta: sin confirmación de "
    "largo cuando el cierre está por debajo del VWAP, sin confirmación de corto cuando el cierre "
    "está por encima del VWAP (la evidencia extra del RSI solo se permite en divergencia ES/MNQ); "
    "(6) Riesgo: invalidación estructural en el máximo/mínimo de oscilación, y la distancia del "
    "stop debe caber en el límite de riesgo máximo o la puerta falla.\n"
    "Estrategia B — Extremos del Rango Exterior (Outer Range Extremes, v1.0): identifica el rango "
    "establecido de 15m (resistencia superior, soporte inferior); evalúa operaciones SOLO en los "
    "límites — límite superior para cortos, límite inferior para largos, el centro del rango es "
    "siempre ESPERAR (WAIT); requiere una confirmación de vela envolvente en el límite (una sola "
    "mecha no es suficiente); lee confirmación de 15m -> sesgo de 5m -> entrada de 1m y trata "
    "cualquier conflicto entre temporalidades como ESPERAR; el VWAP, la EMA21 y el RSI14 son solo "
    "evidencia de apoyo y nunca establecen una operación por sí mismos; define la invalidación "
    "estructural y el riesgo en dólares ANTES de entrar — si el stop estructural supera el límite "
    "de riesgo, ESPERA; define las salidas antes de entrar y registra cada decisión en el diario — "
    "una ESPERA disciplinada es seguir las reglas con éxito.\n"
    "HOLD frente a WAIT: HOLD (MANTENER) significa que una señal o estado existente se mantiene — "
    "sin acción nueva y sin nada nuevo que confirmar. WAIT (ESPERAR) significa que ahora no hay "
    "una operación válida — una puerta falló, las temporalidades están en conflicto, el precio "
    "está en el centro del rango o el riesgo no cabe — así que la acción correcta es quedarse "
    "fuera hasta que cambien las condiciones.\n"
    "Integridad de datos: nombra la etiqueta de los datos antes de interpretar — REAL-TIME (EN "
    "VIVO) son datos reales del mercado, DELAYED (RETRASADO) significa que la fuente va detrás "
    "del mercado, PAPER/SIM/TEST son datos simulados de práctica. Separa siempre las observaciones "
    "(lo que muestran los datos) de las interpretaciones (lo que pueden significar). Nada de lo "
    "que digas es una orden, una instrucción de ejecución ni una prueba de rendimiento operativo.\n"
    "Responde siempre en exactamente estas cinco secciones etiquetadas, en orden, texto plano, "
    "sin markdown:\n"
    "Sesión: ...\nUbicación: ...\nGatillo: ...\nRiesgo: ...\nRevisión: ...\n"
    "Nunca garantices ganancias, nunca des asesoramiento financiero personalizado y rechaza "
    "cualquier solicitud de colocar, enrutar, modificar o cancelar órdenes — no puedes ejecutar "
    "operaciones. Mantén la respuesta por debajo de 280 palabras. No escribas un aviso legal; "
    "la plataforma lo agrega."
)
# Backward-compatible alias (server.py imports METHOD_PROMPT for /ai/analyze).
METHOD_PROMPT = METHOD_PROMPT_EN

_EXEC_RE = re.compile(
    r"\b(place|execute|submit|send|route|enter|open|close|flatten|cancel|modify)\b.{0,40}\b(order|trade|position|contract|long|short)s?\b"
    r"|\b(buy|sell)\s+(\d+|one|a|an|some|mnq|nq|contracts?)\b"
    r"|\b(go|get)\s+(long|short)\b(?!.*\?)"
    # Spanish parity: execution verbs must hit the same refusal screen.
    r"|\b(coloca|colocar|ejecuta|ejecutar|env[ií]a|enviar|enruta|enrutar|cancela|cancelar|modifica|modificar|cierra|cerrar|abre|abrir)\b.{0,40}\b(orden|órdenes|operaci[oó]n|operaciones|posici[oó]n|contrato|contratos|largo|corto)s?\b"
    r"|\b(compra|comprar|vende|vender)\s+(\d+|uno|un|una|algunos|mnq|nq|contratos?)\b",
    re.IGNORECASE,
)

REFUSAL_BODY = (
    "Session: I can't place, route, modify, or cancel orders — Scalp Copilot is education only and has no execution access.\n"
    "Location: Review where price sits versus VWAP and the EMA21 spine on your own chart.\n"
    "Trigger: Confirm 15m structure, 5m bias, then 1m alignment before you act in your own platform.\n"
    "Risk: Define the stop and size first; respect the $100 daily loss lockout.\n"
    "Review: Log the setup in your journal after the session, win or lose."
)
REFUSAL_BODY_ES = (
    "Sesión: No puedo colocar, enrutar, modificar ni cancelar órdenes — Scalp Copilot es solo educación y no tiene acceso de ejecución.\n"
    "Ubicación: Revisa dónde está el precio frente al VWAP y la columna EMA21 en tu propio gráfico.\n"
    "Gatillo: Confirma la estructura de 15m, el sesgo de 5m y luego la alineación de 1m antes de actuar en tu propia plataforma.\n"
    "Riesgo: Define primero el stop y el tamaño; respeta el bloqueo diario de pérdida de $100.\n"
    "Revisión: Registra la operación en tu diario después de la sesión, ganes o pierdas."
)


def normalize_language(value: Any) -> str:
    """Only 'en' and 'es' exist; anything Spanish-prefixed is 'es', else 'en'."""
    return "es" if str(value or "en").strip().lower().startswith("es") else "en"


def method_prompt_for(language: str) -> str:
    return METHOD_PROMPT_ES if normalize_language(language) == "es" else METHOD_PROMPT_EN


def disclaimer_for(language: str) -> str:
    return DISCLAIMER_ES if normalize_language(language) == "es" else DISCLAIMER


def refusal_for(language: str) -> str:
    return REFUSAL_BODY_ES if normalize_language(language) == "es" else REFUSAL_BODY


def copilot_enabled() -> bool:
    return os.environ.get("COPILOT_ENABLED", "false").strip().lower() == "true"


def retention_days() -> int:
    """Conversation retention window in days (COPILOT_RETENTION_DAYS, default 30)."""
    try:
        return max(1, int(os.environ.get("COPILOT_RETENTION_DAYS", "30")))
    except (TypeError, ValueError):
        return 30


async def prune_expired_history(db: Any, user_id: str) -> None:
    """Drop this user's copilot messages and session records older than the
    retention window. Invoked at chat entry so history cannot grow forever."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days())).isoformat()
    await db.copilot_messages.delete_many({"user_id": user_id, "created_at": {"$lt": cutoff}})
    await db.copilot_sessions.delete_many({"user_id": user_id, "created_at": {"$lt": cutoff}})


def is_execution_request(text: str) -> bool:
    return bool(_EXEC_RE.search(text or ""))


def with_disclaimer(text: str, language: str = "en") -> str:
    disc = disclaimer_for(language)
    text = (text or "").rstrip()
    if text.endswith(disc):
        return text
    return f"{text}\n\n{disc}"


class CopilotBody(BaseModel):
    session_id: str = Field(min_length=1, max_length=80)
    message: str = Field(min_length=1, max_length=2000)
    provider: str = "gpt"
    model: str = "gpt-5.4"
    language: str = "en"


# provider signature: (provider, model, system, message, session_id) -> async iterator of str chunks
Provider = Callable[[str, str, str, str, str], AsyncIterator[str]]

# per-provider stream signature: (model, system, message, session_id) -> async iterator of str chunks
ProviderStream = Callable[[str, str, str, str], AsyncIterator[str]]


class ProviderRegistry:
    """Shared intelligence layer: one registry mapping provider name -> a
    stream callable with a common signature. The chat route dispatches
    through a single Provider built from this registry, so OpenAI, Grok,
    or any future provider plug in identically (timeout policy lives in
    each provider callable / the shim constant)."""

    def __init__(self) -> None:
        self._providers: Dict[str, ProviderStream] = {}

    def register(self, name: str, stream_fn: ProviderStream) -> ProviderStream:
        self._providers[name.strip().lower()] = stream_fn
        return stream_fn

    def names(self) -> List[str]:
        return sorted(self._providers)

    async def stream(
        self, provider: str, model: str, system: str, message: str, session_id: str
    ) -> AsyncIterator[str]:
        fn = self._providers.get((provider or "").strip().lower())
        if fn is None:
            raise ValueError(f"Unknown copilot provider: {provider!r}")
        async for chunk in fn(model, system, message, session_id):
            yield chunk


def build_provider_dispatch(providers: Dict[str, ProviderStream]) -> Provider:
    """Build the single (provider, model, system, message, session_id)
    dispatch callable the chat route consumes, from a name->stream map."""
    registry = ProviderRegistry()
    for name, stream_fn in providers.items():
        registry.register(name, stream_fn)
    return registry.stream


class UsageChunk:
    """Optional stream event a provider callable may yield (conventionally
    last) to report token usage for accounting. The chat route consumes it;
    it is never forwarded to the client. Providers that cannot supply
    usage simply never yield one, and the usage record stores null."""

    def __init__(self, usage: Optional[Dict[str, Any]] = None) -> None:
        self.usage = usage


async def record_usage(
    db: Any,
    *,
    session_id: str,
    user_id: str,
    provider: str,
    model: str,
    language: str,
    latency_ms: int,
    usage: Optional[Dict[str, Any]],
    created_at: str,
) -> None:
    """Append one row to copilot_usage. NEVER contains credentials — only
    provider/model names, latency, and provider-reported token counts."""
    coll = getattr(db, "copilot_usage", None)
    if coll is None:
        return
    await coll.insert_one({
        "session_id": session_id,
        "user_id": user_id,
        "provider": provider,
        "model": model,
        "language": language,
        "latency_ms": latency_ms,
        "usage": usage,
        "created_at": created_at,
    })


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
        lang = normalize_language(body.language)
        msg = body.message.strip()
        if not msg:
            raise HTTPException(status_code=400, detail="Empty message")
        await _owned_session(body.session_id, user_id)
        await prune_expired_history(db, user_id)
        now = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731
        await db.copilot_messages.insert_one({
            "session_id": body.session_id, "user_id": user_id, "role": "user", "content": msg, "created_at": now(),
        })

        if is_execution_request(msg):
            text = with_disclaimer(refusal_for(lang), lang)
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
        if lang == "es":
            context_head = "CONTEXTO DEL ESCRITORIO PAPER/SIM (no es en vivo, no es prueba de rendimiento):"
            convo_head = "CONVERSACIÓN HASTA AHORA:"
        else:
            context_head = "PAPER/SIM DESK CONTEXT (not live, not performance proof):"
            convo_head = "CONVERSATION SO FAR:"
        system = f"{method_prompt_for(lang)}\n\n{context_head}\n{context}\n\n{convo_head}\n{transcript}"
        provider = "grok" if body.provider.lower() == "grok" and os.environ.get("XAI_API_KEY") else "gpt"
        model = "grok-4.6" if provider == "grok" else (body.model if body.model in GPT_MODELS else "gpt-5.4")

        async def gen():
            parts: List[str] = []
            usage: Optional[Dict[str, Any]] = None
            started = time.perf_counter()
            try:
                async for chunk in stream_provider(provider, model, system, msg, body.session_id):
                    if isinstance(chunk, UsageChunk):
                        usage = chunk.usage
                        continue
                    if chunk:
                        parts.append(chunk)
                        yield chunk
            except Exception as e:  # never leak provider errors/keys
                if logger:
                    logger.error(f"Copilot stream error ({provider}): {type(e).__name__}")
                parts.append("\n[Copilot hit an error — try again.]")
                yield parts[-1]
            latency_ms = round((time.perf_counter() - started) * 1000)
            tail = "\n\n" + disclaimer_for(lang)
            yield tail
            await db.copilot_messages.insert_one({
                "session_id": body.session_id, "user_id": user_id, "role": "assistant",
                "content": "".join(parts) + tail, "provider": provider, "model": model, "created_at": now(),
            })
            await record_usage(
                db,
                session_id=body.session_id, user_id=user_id, provider=provider, model=model,
                language=lang, latency_ms=latency_ms, usage=usage, created_at=now(),
            )

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

    @router.delete("/history/{session_id}")
    async def copilot_delete_history(session_id: str, request: Request):
        _gate()
        user = await get_current_user(request, db)
        sess = await db.copilot_sessions.find_one({"session_id": session_id}, {"_id": 0})
        if sess and sess.get("user_id") != user["user_id"]:
            raise HTTPException(status_code=403, detail="Forbidden")
        res = await db.copilot_messages.delete_many(
            {"session_id": session_id, "user_id": user["user_id"]}
        )
        await db.copilot_sessions.delete_many(
            {"session_id": session_id, "user_id": user["user_id"]}
        )
        return {"deleted": getattr(res, "deleted_count", 0)}

    return router


def new_session_id() -> str:
    return uuid.uuid4().hex
