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
    def _match(d, q): return all(d.get(k) == v for k, v in q.items())
    @staticmethod
    def _proj(d, p): return {k: v for k, v in d.items() if k != "_id" and (not any(p.get(x) == 1 for x in p) or p.get(k) == 1)}
    async def find_one(self, q, p=None):
        for d in self.docs:
            if self._match(d, q): return self._proj(d, p or {})
        return None
    async def insert_one(self, d): self.docs.append(dict(d))
    def find(self, q, p=None): return _Cursor([self._proj(d, p or {}) for d in self.docs if self._match(d, q)])


class _DB:
    def __init__(self): self.copilot_sessions = _Coll(); self.copilot_messages = _Coll()


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
