"""In-process copilot tests — providers and DB mocked, no network, no keys."""
import os
import sys

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import copilot  # noqa: E402
from copilot import DISCLAIMER, SECTIONS, build_copilot_router  # noqa: E402


class _Cursor:
    def __init__(self, rows): self.rows = rows
    def sort(self, key, direction): self.rows.sort(key=lambda r: r.get(key, "")); return self
    async def to_list(self, n): return self.rows[:n]


class _Coll:
    def __init__(self): self.docs = []
    @staticmethod
    def _match(d, q):
        for k, v in q.items():
            if isinstance(v, dict) and "$lt" in v:
                if not (d.get(k) is not None and d.get(k) < v["$lt"]): return False
            elif d.get(k) != v:
                return False
        return True
    @staticmethod
    def _proj(d, p): return {k: v for k, v in d.items() if k != "_id" and (not any(p.get(x) == 1 for x in p) or p.get(k) == 1)}
    async def find_one(self, q, p=None):
        for d in self.docs:
            if self._match(d, q): return self._proj(d, p or {})
        return None
    async def insert_one(self, d): self.docs.append(dict(d))
    async def delete_many(self, q):
        before = len(self.docs)
        self.docs = [d for d in self.docs if not self._match(d, q)]
        return type("R", (), {"deleted_count": before - len(self.docs)})()
    def find(self, q, p=None): return _Cursor([self._proj(d, p or {}) for d in self.docs if self._match(d, q)])


class _DB:
    def __init__(self): self.copilot_sessions = _Coll(); self.copilot_messages = _Coll(); self.copilot_usage = _Coll()


async def fake_user(request: Request, db):
    uid = request.headers.get("X-Test-User")
    if not uid:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"user_id": uid}


CALLS = []
FIVE = "Session: NY AM.\nLocation: above VWAP.\nTrigger: 15m->5m->1m aligned on EMA21.\nRisk: 8pt stop.\nReview: journal it."


async def fake_provider(provider, model, system, msg, session_id):
    CALLS.append({"provider": provider, "system": system})
    for part in FIVE.split("\n"):
        yield part + "\n"


async def fake_ctx():
    return "DATA MODE: PAPER/SIM/TEST"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("COPILOT_ENABLED", "true")
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test-SECRET-123")
    monkeypatch.setenv("XAI_API_KEY", "xai-test-SECRET-456")
    CALLS.clear()
    app = FastAPI()
    app.include_router(build_copilot_router(_DB(), fake_user, fake_ctx, fake_provider), prefix="/api")
    return TestClient(app)


A = {"X-Test-User": "user_a"}
B = {"X-Test-User": "user_b"}


def _chat(c, msg="How do I read this setup?", sid="s1", h=A):
    return c.post("/api/copilot/chat", json={"session_id": sid, "message": msg}, headers=h)


def test_flag_off_404(client, monkeypatch):
    monkeypatch.setenv("COPILOT_ENABLED", "false")
    assert _chat(client).status_code == 404
    assert client.get("/api/copilot/history/s1", headers=A).status_code == 404


def test_flag_default_is_off(monkeypatch):
    monkeypatch.delenv("COPILOT_ENABLED", raising=False)
    assert copilot.copilot_enabled() is False


def test_401_without_login(client):
    assert _chat(client, h={}).status_code == 401
    assert client.get("/api/copilot/history/s1").status_code == 401


def test_cross_user_history_and_chat_forbidden(client):
    assert _chat(client).status_code == 200
    assert client.get("/api/copilot/history/s1", headers=B).status_code == 403
    assert _chat(client, sid="s1", h=B).status_code == 403
    assert client.get("/api/copilot/history/unknown", headers=B).json() == []
    own = client.get("/api/copilot/history/s1", headers=A).json()
    assert [m["role"] for m in own] == ["user", "assistant"]


def test_status_public_booleans_only(client):
    r = client.get("/api/copilot/status")
    assert r.status_code == 200
    body = r.json()
    assert body == {"enabled": True, "providers": {"gpt": True, "grok": True}}
    assert "SECRET" not in r.text and "sk-" not in r.text and "xai-" not in r.text


def test_disclaimer_always_appended(client):
    r = _chat(client)
    assert r.text.rstrip().endswith(DISCLAIMER)


def test_five_sections_and_method_prompt(client):
    r = _chat(client)
    for s in SECTIONS:
        assert f"{s}:" in r.text
    system = CALLS[-1]["system"]
    assert "EMA21" in system and "VWAP" in system and "15m structure -> 5m bias -> 1m entry" in system
    assert "Do NOT use an EMA9 cross or RSI cross" in system
    assert "No financial advice disclaimers" not in system


@pytest.mark.parametrize("msg", ["Buy 2 MNQ now", "place a long order at 21000", "flatten my position", "go long"])
def test_execution_request_refused_without_provider_call(client, msg):
    r = _chat(client, msg=msg)
    assert r.status_code == 200
    assert "can't place, route, modify, or cancel orders" in r.text
    assert r.text.rstrip().endswith(DISCLAIMER)
    for s in SECTIONS:
        assert f"{s}:" in r.text
    assert CALLS == []


def test_server_has_no_disclaimer_bypass_and_gates_ai_analyze():
    src = open(os.path.join(os.path.dirname(__file__), "..", "server.py")).read()
    assert "No financial advice disclaimers" not in src
    i = src.index('@api_router.post("/ai/analyze")')
    assert "if not copilot_enabled():" in src[i:i + 400]
    assert "EMA9/EMA21 \"\n        \"cross + VWAP + RSI14" not in src


def _chat_lang(c, msg="¿Cómo leo este escenario?", sid="s-es", h=A, lang="es"):
    return c.post("/api/copilot/chat",
                  json={"session_id": sid, "message": msg, "language": lang}, headers=h)


def test_spanish_prompt_and_disclaimer(client):
    r = _chat_lang(client)
    assert r.status_code == 200
    assert r.text.rstrip().endswith(copilot.DISCLAIMER_ES)
    assert not r.text.rstrip().endswith(DISCLAIMER)
    system = CALLS[-1]["system"]
    assert "Eres Scalp Copilot" in system
    assert "Sesión: ..." in system and "Gatillo: ..." in system
    assert "CONTEXTO DEL ESCRITORIO PAPER/SIM" in system


def test_spanish_refusal_without_provider_call(client):
    r = _chat_lang(client, msg="compra 2 MNQ ahora", sid="s-es2")
    assert r.status_code == 200
    assert "No puedo colocar, enrutar, modificar ni cancelar órdenes" in r.text
    assert r.text.rstrip().endswith(copilot.DISCLAIMER_ES)
    for s in copilot.SECTIONS_ES:
        assert f"{s}:" in r.text
    assert CALLS == []


def test_english_is_default_and_unchanged(client):
    r = client.post("/api/copilot/chat",
                    json={"session_id": "s-en", "message": "How do I read this setup?"}, headers=A)
    assert r.status_code == 200
    assert r.text.rstrip().endswith(DISCLAIMER)
    system = CALLS[-1]["system"]
    assert "You are Scalp Copilot" in system
    assert "PAPER/SIM DESK CONTEXT" in system
    assert copilot.normalize_language("fr") == "en"
    assert copilot.normalize_language("es-ES") == "es"
    assert copilot.method_prompt_for("en") is copilot.METHOD_PROMPT


def test_method_prompt_teaches_named_strategies_en():
    p = copilot.METHOD_PROMPT_EN
    # Strategy A — Six Gates, as implemented/documented
    assert "Strategy A — Six Gates" in p
    for gate in ("Location:", "Activity:", "Candle close:", "Retest / no-chase:", "Alignment:", "Risk:"):
        assert gate in p
    assert "no long confirmation when close is below VWAP" in p
    assert "no short confirmation when close is above VWAP" in p
    # Strategy B — Outer Range Extremes v1.0
    assert "Strategy B — Outer Range Extremes (v1.0)" in p
    assert "engulfing candlestick confirmation" in p
    assert "mid-range is always WAIT" in p
    assert "supporting evidence only" in p
    assert "a disciplined WAIT is successful rule-following" in p
    # HOLD vs WAIT + data integrity + safety framing
    assert "HOLD vs WAIT" in p
    assert "REAL-TIME" in p and "DELAYED" in p and "PAPER/SIM/TEST" in p
    assert "observations" in p and "interpretations" in p
    assert "not an order" in p or "Nothing you say is an order" in p


def test_method_prompt_teaches_named_strategies_es():
    p = copilot.METHOD_PROMPT_ES
    assert "Estrategia A — Seis Puertas (Six Gates)" in p
    assert "Estrategia B — Extremos del Rango Exterior (Outer Range Extremes, v1.0)" in p
    assert "vela envolvente" in p
    assert "el centro del rango es siempre ESPERAR (WAIT)" in p
    assert "solo evidencia de apoyo" in p
    assert "HOLD frente a WAIT" in p
    assert "REAL-TIME" in p and "DELAYED" in p and "PAPER/SIM/TEST" in p
    assert "observaciones" in p and "interpretaciones" in p
    assert "sin confirmación de largo cuando el cierre está por debajo del VWAP" in p


def test_chat_system_prompt_carries_methodology(client):
    _chat(client, sid="s-meth")
    system = CALLS[-1]["system"]
    assert "Strategy A — Six Gates" in system and "Outer Range Extremes" in system
    _chat_lang(client, sid="s-meth-es")
    system = CALLS[-1]["system"]
    assert "Estrategia A — Seis Puertas" in system and "Outer Range Extremes" in system


def test_delete_history_owner_only(client):
    assert _chat(client, sid="s-del").status_code == 200
    assert client.delete("/api/copilot/history/s-del", headers=B).status_code == 403
    assert len(client.get("/api/copilot/history/s-del", headers=A).json()) == 2
    r = client.delete("/api/copilot/history/s-del", headers=A)
    assert r.status_code == 200 and r.json()["deleted"] == 2
    assert client.get("/api/copilot/history/s-del", headers=A).json() == []
    assert client.delete("/api/copilot/history/s-del").status_code == 401


@pytest.mark.asyncio
async def test_prune_expired_history(monkeypatch):
    monkeypatch.setenv("COPILOT_RETENTION_DAYS", "30")
    assert copilot.retention_days() == 30
    db = _DB()
    old = "2020-01-01T00:00:00+00:00"
    fresh = "2999-01-01T00:00:00+00:00"
    db.copilot_messages.docs = [
        {"session_id": "s1", "user_id": "user_a", "role": "user", "content": "old", "created_at": old},
        {"session_id": "s1", "user_id": "user_a", "role": "user", "content": "fresh", "created_at": fresh},
        {"session_id": "s2", "user_id": "user_b", "role": "user", "content": "other user old", "created_at": old},
    ]
    db.copilot_sessions.docs = [
        {"session_id": "s1", "user_id": "user_a", "created_at": old},
        {"session_id": "s2", "user_id": "user_b", "created_at": old},
    ]
    await copilot.prune_expired_history(db, "user_a")
    kept = {(d["user_id"], d["content"]) for d in db.copilot_messages.docs}
    assert kept == {("user_a", "fresh"), ("user_b", "other user old")}
    assert [s["user_id"] for s in db.copilot_sessions.docs] == ["user_b"]


def test_retention_default_and_invalid(monkeypatch):
    monkeypatch.delenv("COPILOT_RETENTION_DAYS", raising=False)
    assert copilot.retention_days() == 30
    monkeypatch.setenv("COPILOT_RETENTION_DAYS", "not-a-number")
    assert copilot.retention_days() == 30
    monkeypatch.setenv("COPILOT_RETENTION_DAYS", "7")
    assert copilot.retention_days() == 7


@pytest.mark.asyncio
async def test_provider_dispatch_routes_both_providers():
    seen = []

    async def gpt_stream(model, system, message, session_id):
        seen.append(("gpt", model, message, session_id))
        yield "gpt-chunk"

    async def grok_stream(model, system, message, session_id):
        seen.append(("grok", model, message, session_id))
        yield "grok-chunk"

    dispatch = copilot.build_provider_dispatch({"gpt": gpt_stream, "grok": grok_stream})
    assert [c async for c in dispatch("gpt", "gpt-5.4", "sys", "hi", "s1")] == ["gpt-chunk"]
    assert [c async for c in dispatch("Grok", "grok-4.6", "sys", "hola", "s2")] == ["grok-chunk"]
    assert seen == [("gpt", "gpt-5.4", "hi", "s1"), ("grok", "grok-4.6", "hola", "s2")]
    with pytest.raises(ValueError, match="Unknown copilot provider"):
        [c async for c in dispatch("nope", "m", "sys", "hi", "s3")]

    reg = copilot.ProviderRegistry()
    reg.register("GPT", gpt_stream)
    assert reg.names() == ["gpt"]


async def _usage_provider(provider, model, system, msg, session_id):
    yield "answer chunk"
    yield copilot.UsageChunk(usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15})


def _usage_client(monkeypatch, provider_fn):
    monkeypatch.setenv("COPILOT_ENABLED", "true")
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test-SECRET-123")
    db = _DB()
    app = FastAPI()
    app.include_router(build_copilot_router(db, fake_user, fake_ctx, provider_fn), prefix="/api")
    return TestClient(app), db


def test_usage_recorded_with_provider_supplied_tokens(monkeypatch):
    c, db = _usage_client(monkeypatch, _usage_provider)
    r = c.post("/api/copilot/chat", json={"session_id": "s-u1", "message": "How do I read this setup?"}, headers=A)
    assert r.status_code == 200
    assert "answer chunk" in r.text
    assert "prompt_tokens" not in r.text  # usage event never reaches the client
    assert len(db.copilot_usage.docs) == 1
    rec = db.copilot_usage.docs[0]
    assert rec["provider"] == "gpt" and rec["model"] == "gpt-5.4"
    assert rec["user_id"] == "user_a" and rec["session_id"] == "s-u1"
    assert isinstance(rec["latency_ms"], int) and rec["latency_ms"] >= 0
    assert rec["usage"] == {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
    assert "SECRET" not in str(rec) and "sk-" not in str(rec)


def test_usage_recorded_null_when_provider_supplies_none(monkeypatch):
    c, db = _usage_client(monkeypatch, fake_provider)
    r = c.post("/api/copilot/chat", json={"session_id": "s-u2", "message": "How do I read this setup?"}, headers=A)
    assert r.status_code == 200
    assert len(db.copilot_usage.docs) == 1
    rec = db.copilot_usage.docs[0]
    assert rec["provider"] == "gpt" and rec["model"] == "gpt-5.4" and rec["usage"] is None


def test_refusal_writes_no_usage_record(monkeypatch):
    c, db = _usage_client(monkeypatch, _usage_provider)
    r = c.post("/api/copilot/chat", json={"session_id": "s-u3", "message": "Buy 2 MNQ now"}, headers=A)
    assert r.status_code == 200
    assert db.copilot_usage.docs == []
