"""POST /ai/analyze must require a logged-in user (P0-1 hardening).

Self-contained: in-memory mongo, real JWTs, LLM + market-data fetches mocked,
no network, no live backend. Mirrors the test_admin_auth.py pattern.
"""
import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "unit-test-only-secret")
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1")  # never contacted; db is swapped below
mongomock_motor = pytest.importorskip("mongomock_motor")

import auth  # noqa: E402
import server  # noqa: E402
from copilot import DISCLAIMER  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class _FakeChat:
    """Stand-in for the shim LlmChat: no provider call, fixed text."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def with_model(self, provider, model):
        return self

    async def send_message(self, message):
        return "Fake educational analysis."


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("COPILOT_ENABLED", "true")
    monkeypatch.setenv("EMERGENT_LLM_KEY", "sk-test-SECRET-123")
    db = mongomock_motor.AsyncMongoMockClient()["t"]
    monkeypatch.setattr(server, "db", db)
    _run(db.users.insert_one({"user_id": "u1", "email": "u1@x.test", "role": "user"}))

    async def fake_quote(symbol):
        return {"price": 100.0, "change_percent": 0.5, "volume": 1000}

    async def fake_indicators(symbol):
        return {"ema9": 99.0, "ema21": 98.0, "rsi": 50.0}

    monkeypatch.setattr(server, "fetch_stock_quote", fake_quote)
    monkeypatch.setattr(server, "fetch_technical_indicators", fake_indicators)
    monkeypatch.setattr(server, "LlmChat", _FakeChat)
    headers = {"Authorization": f"Bearer {auth.create_access_token('u1', 'u1@x.test')}"}
    return TestClient(server.app), headers


BODY = {"symbol": "MNQ", "analysis_type": "general"}


def test_unauthenticated_401(client):
    c, _ = client
    assert c.post("/api/ai/analyze", json=BODY).status_code == 401


def test_bad_token_401(client):
    c, _ = client
    r = c.post("/api/ai/analyze", json=BODY, headers={"Authorization": "Bearer bogus"})
    assert r.status_code == 401


def test_authenticated_still_works(client):
    c, headers = client
    r = c.post("/api/ai/analyze", json=BODY, headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "MNQ"
    assert body["analysis_type"] == "general"
    assert body["analysis"].startswith("Fake educational analysis.")
    assert body["analysis"].endswith(DISCLAIMER)
    assert body["data_used"]["quote"]["price"] == 100.0


def test_flag_off_404_even_authenticated(client, monkeypatch):
    c, headers = client
    monkeypatch.setenv("COPILOT_ENABLED", "false")
    assert c.post("/api/ai/analyze", json=BODY, headers=headers).status_code == 404
