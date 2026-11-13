"""PR #15 Vercel-validate-then-forward contract vs Emergent POST /api/signals/tradingview.

These tests simulate what frontend/api/signals/tradingview.js (PR #15) sends after
it validates the Vercel-side secret and swaps in EMERGENT_WEBHOOK_SECRET:
a JSON POST, Content-Type application/json, secret in the body only, original
alert fields passed through verbatim. They do not import or edit PR #15's files.
No trading execution is implied; HOLD records a non-executed feed row only.
"""
import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "unit-test-only-secret")
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1")
mongomock_motor = pytest.importorskip("mongomock_motor")

import server  # noqa: E402

DUMMY = "test-secret-dummy"
P = "/api/signals/tradingview"

# Fields PR #15 forwards verbatim, plus extras a TradingView alert may carry.
PR15_FORWARD = {
    "secret": DUMMY,
    "action": "HOLD",
    "symbol": "MNQ1!",
    "interval": "15",
    "price": 28450.25,
    "time": "2026-11-13T11:00:00Z",
    "source": "MNQ Strategy B",
    "note": "info-only HOLD — no card",
    "strategy": "B",
    "state": "NO TRADE",
    "vwap": 28400.0,
    "rsi": 55,
    "gates": "G1",
}


@pytest.fixture
def ctx(monkeypatch):
    db = mongomock_motor.AsyncMongoMockClient()["pr15"]
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "SIGNAL_WEBHOOK_SECRET", DUMMY)
    monkeypatch.setitem(server.signal_engine_state, "kill_switch", False)
    monkeypatch.delenv("TEMPORAL_ENABLED", raising=False)

    async def _no_discord(doc):
        return False

    monkeypatch.setattr(server, "send_discord_signal", _no_discord)
    return TestClient(server.app), db


def test_pr15_forward_body_secret_hold_accepted(ctx):
    """Vercel forwards secret in the JSON body and no auth header."""
    c, db = ctx
    r = c.post(P, json=PR15_FORWARD)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["action"] == "HOLD"
    assert body["executed"] is False
    assert body["status"] == "held"
    assert asyncio.run(db.signals.count_documents({"action": "HOLD"})) == 1


def test_pr15_forward_buy_passthrough_fields_create_card(ctx):
    payload = dict(PR15_FORWARD, action="BUY")
    c, _ = ctx
    r = c.post(P, json=payload)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "created"
    assert body["side"] == "long"
    assert body["price"] == 28450.25
    assert body["is_test"] is False


def test_pr15_forward_wrong_secret_401_json(ctx):
    c, _ = ctx
    r = c.post(P, json=dict(PR15_FORWARD, secret="WRONG"))
    assert r.status_code == 401
    assert "application/json" in r.headers.get("content-type", "")
    assert "detail" in r.json()


def test_pr15_forward_missing_secret_401_json(ctx):
    c, _ = ctx
    body = dict(PR15_FORWARD)
    body.pop("secret")
    r = c.post(P, json=body)
    assert r.status_code == 401
    assert "detail" in r.json()


def test_pr15_secret_unset_503_json(ctx, monkeypatch):
    c, _ = ctx
    monkeypatch.setattr(server, "SIGNAL_WEBHOOK_SECRET", "")
    r = c.post(P, json=PR15_FORWARD)
    assert r.status_code == 503
    assert r.json()["detail"] == "Webhook disabled: secret not configured"


def test_pr15_lowercase_header_accepted(ctx):
    """Starlette treats header names as case-insensitive (x-webhook-secret)."""
    c, _ = ctx
    r = c.post(
        P,
        json={"action": "HOLD", "symbol": "MNQ1!", "interval": "1", "price": 28450.25, "time": "2026-11-13T11:00:00Z", "source": "header-check"},
        headers={"x-webhook-secret": DUMMY},
    )
    assert r.status_code == 200, r.text
    assert r.json()["action"] == "HOLD"
    assert r.json()["executed"] is False


def test_pr15_forward_responses_are_json(ctx):
    c, _ = ctx
    for payload, code in (
        (PR15_FORWARD, 200),
        (dict(PR15_FORWARD, secret="nope"), 401),
        (dict(PR15_FORWARD, action="NOT_A_REAL_ACTION"), 400),
    ):
        r = c.post(P, json=payload)
        assert r.status_code == code, (code, r.text)
        assert "application/json" in r.headers.get("content-type", "")
        assert isinstance(r.json(), dict)
