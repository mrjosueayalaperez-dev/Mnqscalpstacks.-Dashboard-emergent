"""Webhook secret rules + Temporal hand-off on both TradingView routes (in-process, mongomock)."""
import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "unit-test-only-secret")
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1")  # never contacted; db is swapped below
mongomock_motor = pytest.importorskip("mongomock_motor")

import server  # noqa: E402
from temporal import ingest_client  # noqa: E402

DUMMY = "test-secret-dummy"
P = "/api/signals/tradingview"
L = "/api/webhook/tradingview"


@pytest.fixture
def ctx(monkeypatch):
    db = mongomock_motor.AsyncMongoMockClient()["routes"]
    monkeypatch.setattr(server, "db", db)
    monkeypatch.setattr(server, "SIGNAL_WEBHOOK_SECRET", DUMMY)
    monkeypatch.setitem(server.signal_engine_state, "kill_switch", False)
    monkeypatch.delenv("TEMPORAL_ENABLED", raising=False)
    async def _no_discord(doc):
        return False

    monkeypatch.setattr(server, "send_discord_signal", _no_discord)
    return TestClient(server.app), db


def _count(db, coll, q=None):
    return asyncio.run(getattr(db, coll).count_documents(q or {}))


def test_secret_unset_returns_503_both_routes(ctx, monkeypatch):
    c, _ = ctx
    monkeypatch.setattr(server, "SIGNAL_WEBHOOK_SECRET", "")
    r = c.post(P, json={"secret": "anything", "action": "BUY", "price": 29900})
    assert r.status_code == 503 and r.json()["detail"] == "Webhook disabled: secret not configured"
    assert c.post(L, json={"type": "buy", "price": "29900"}).status_code == 503


def test_wrong_secret_401(ctx):
    c, _ = ctx
    assert c.post(P, json={"secret": "WRONG", "action": "BUY", "price": 29900}).status_code == 401
    assert c.post(L, json={"secret": "WRONG", "type": "buy", "price": "29900"}).status_code == 401


def test_query_only_secret_is_rejected(ctx):
    c, _ = ctx
    assert c.post(f"{P}?secret={DUMMY}", json={"action": "BUY", "price": 29900}).status_code == 401
    assert c.post(f"{P}?secret={DUMMY}", content="BUY MNQ1! 29900.25").status_code == 401
    assert c.post(f"{L}?secret={DUMMY}", json={"type": "buy", "price": "29900"}).status_code == 401


def test_legacy_without_secret_401(ctx):
    c, _ = ctx
    assert c.post(L, json={"type": "buy", "symbol": "MNQ", "price": "29900"}).status_code == 401


def test_header_secret_ok_sync_path(ctx):
    c, db = ctx
    r = c.post(P, content="BUY MNQ1! 29900.25", headers={"X-Webhook-Secret": DUMMY})
    assert r.status_code == 200 and r.json()["status"] == "created" and r.json()["is_test"] is False
    r = c.post(L, json={"type": "sell", "symbol": "MNQ", "price": "29950"}, headers={"X-Webhook-Secret": DUMMY})
    assert r.status_code == 200 and r.json()["status"] == "received" and r.json()["side"] == "short"
    assert _count(db, "signals") == 2


def test_body_secret_ok_sync_path(ctx):
    c, _ = ctx
    r = c.post(P, json={"secret": DUMMY, "action": "SELL", "symbol": "NQ1!", "price": 29900.25})
    assert r.status_code == 200 and r.json()["status"] == "created"
    r = c.post(L, json={"secret": DUMMY, "type": "buy", "symbol": "MNQ", "price": "29900"})
    assert r.status_code == 200 and r.json()["status"] == "received"


def test_disabled_keeps_existing_sync_semantics(ctx, monkeypatch):
    c, _ = ctx
    body = {"secret": DUMMY, "action": "HOLD"}
    r = c.post(P, json=body)
    assert r.json()["message"] == "HOLD accepted — no order placed." and r.json()["executed"] is False
    assert c.post(P, json={"secret": DUMMY, "action": "BUY", "symbol": "ES1!", "price": 1}).status_code == 400
    monkeypatch.setitem(server.signal_engine_state, "kill_switch", True)
    assert c.post(P, json={"secret": DUMMY, "action": "BUY", "price": 29900}).json() == {"status": "blocked", "reason": "Kill switch active"}
    assert c.post(L, json={"secret": DUMMY, "type": "buy", "price": "29900"}).json() == {"status": "blocked", "reason": "Kill switch active"}


def test_price_action_unaffected_and_synchronous(ctx, monkeypatch):
    c, _ = ctx
    monkeypatch.setenv("TEMPORAL_ENABLED", "true")

    async def boom(*a, **k):
        raise AssertionError("PRICE must not start a workflow")

    monkeypatch.setattr(ingest_client, "run_ingest", boom)
    r = c.post(P, json={"secret": DUMMY, "action": "PRICE", "price": 29912.5})
    assert r.status_code == 200 and r.json() == {"ok": True, "action": "PRICE", "price": 29912.5}


def test_enabled_kill_switch_still_blocks_before_workflow(ctx, monkeypatch):
    c, _ = ctx
    monkeypatch.setenv("TEMPORAL_ENABLED", "true")
    monkeypatch.setitem(server.signal_engine_state, "kill_switch", True)

    async def boom(*a, **k):
        raise AssertionError("kill switch must block before Temporal")

    monkeypatch.setattr(ingest_client, "run_ingest", boom)
    assert c.post(P, json={"secret": DUMMY, "action": "BUY", "price": 29900}).json()["status"] == "blocked"
    assert c.post(L, json={"secret": DUMMY, "type": "buy", "price": "29900"}).json()["status"] == "blocked"


def test_enabled_temporal_down_returns_503_and_logs(ctx, monkeypatch):
    c, db = ctx
    monkeypatch.setenv("TEMPORAL_ENABLED", "true")

    async def down():
        raise ConnectionError("connection refused")

    monkeypatch.setattr(ingest_client, "_get_client", down)
    r = c.post(P, json={"secret": DUMMY, "action": "BUY", "price": 29900})
    assert r.status_code == 503 and r.json() == {"detail": "ingest unavailable"}
    r = c.post(L, json={"secret": DUMMY, "type": "buy", "price": "29900"})
    assert r.status_code == 503
    assert _count(db, "signals") == 0  # no local fallback
    assert _count(db, "signal_events", {"status": 503}) == 2


def test_enabled_slow_workflow_returns_202(ctx, monkeypatch):
    c, _ = ctx
    monkeypatch.setenv("TEMPORAL_ENABLED", "true")

    class Handle:
        async def result(self):
            await asyncio.sleep(10)

    class FakeClient:
        async def start_workflow(self, *a, **k):
            return Handle()

    async def fake_client():
        return FakeClient()

    monkeypatch.setattr(ingest_client, "_get_client", fake_client)
    r = c.post(P, json={"secret": DUMMY, "action": "BUY", "price": 29900, "time": "2026-10-29T14:00:00Z"})
    assert r.status_code == 202 and r.json()["status"] == "accepted" and r.json()["workflow_id"].startswith("tv-ingest-")


def test_receiver_status_never_returns_raw_secret(ctx):
    c, _ = ctx
    d = c.get("/api/signals/receiver-status").json()
    assert DUMMY not in str(d)
    assert d["secret_configured"] is True and d["secret_masked"] == "********"
