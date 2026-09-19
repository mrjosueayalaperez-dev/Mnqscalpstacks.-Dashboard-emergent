"""
Iteration 16 — Full regression of the NEW signal punch pipeline endpoints.

Covers /api/signals/tradingview (secret-protected), /api/signals/test-punch,
/api/signals/receiver-status, /api/signals/events, /api/signals/session-filter,
GET /api/signals, /stats, /health, /kill-switch.

Reads SIGNAL_WEBHOOK_SECRET from /app/backend/.env.
"""
import asyncio
import os
import time

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BASE = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else None
# fallback to preview URL from /app/frontend/.env
if not BASE:
    for line in open("/app/frontend/.env"):
        if line.startswith("REACT_APP_BACKEND_URL="):
            BASE = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE}/api"

SECRET = os.environ.get("SIGNAL_WEBHOOK_SECRET", "")


def _reset_active_signals():
    async def _r():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        await client[os.environ["DB_NAME"]].signals.update_many(
            {"status": "active"}, {"$set": {"status": "closed_by_test"}}
        )
        client.close()
    asyncio.run(_r())


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Ensure kill switch off + clean active signals so cooldown does not block
    s.post(f"{API}/signals/kill-switch", json={"enabled": False, "reason": "test start"}, timeout=10)
    _reset_active_signals()
    yield s
    s.post(f"{API}/signals/kill-switch", json={"enabled": False, "reason": "test end"}, timeout=10)


# ---------- Secret validation ----------
def test_secret_configured():
    assert SECRET, "SIGNAL_WEBHOOK_SECRET must be set in /app/backend/.env"


def test_tradingview_bad_secret_returns_401_and_logs(http):
    r = http.post(f"{API}/signals/tradingview", json={
        "secret": "WRONG", "action": "BUY", "symbol": "MNQ1!", "interval": "1", "price": 29900.25,
    }, timeout=10)
    assert r.status_code == 401, r.text
    # Verify event log entry recorded
    ev = http.get(f"{API}/signals/events?limit=5", timeout=10).json()
    assert isinstance(ev, list) and len(ev) > 0
    assert any((not e.get("ok")) and e.get("status") == 401 for e in ev), \
        f"401 event not logged: {ev[:2]}"


def test_tradingview_missing_secret_returns_401(http):
    r = http.post(f"{API}/signals/tradingview", json={
        "action": "BUY", "symbol": "MNQ1!", "interval": "1", "price": 29901.25,
    }, timeout=10)
    assert r.status_code == 401


def test_loose_text_body_has_no_secret_returns_401(http):
    # Text body cannot carry the secret; with secret configured, must be 401
    r = http.post(f"{API}/signals/tradingview",
                  data="SELL MNQ1! 29900.25",
                  headers={"Content-Type": "text/plain"}, timeout=10)
    assert r.status_code == 401, r.text


# ---------- Valid punch creation ----------
def test_tradingview_valid_buy_creates_long_punch(http):
    _reset_active_signals()
    r = http.post(f"{API}/signals/tradingview", json={
        "secret": SECRET, "action": "BUY", "symbol": "MNQ1!", "interval": "1",
        "price": 29910.50, "source": "regression test",
    }, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "created", d
    assert d["side"] == "long"
    assert "signal_id" in d
    assert d.get("is_test") is False
    pytest.buy_id = d["signal_id"]


def test_tradingview_nq1_symbol_accepted(http):
    _reset_active_signals()
    r = http.post(f"{API}/signals/tradingview", json={
        "secret": SECRET, "action": "SELL", "symbol": "NQ1!", "interval": "5",
        "price": 29915.25, "source": "regression test",
    }, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "created"
    assert d["side"] == "short"


def test_tradingview_unsupported_symbol_returns_400(http):
    r = http.post(f"{API}/signals/tradingview", json={
        "secret": SECRET, "action": "BUY", "symbol": "ES1!", "interval": "1", "price": 5000.0,
    }, timeout=10)
    assert r.status_code == 400
    assert "Unsupported" in r.text or "MNQ1!" in r.text


def test_tradingview_close_expires_active_signals(http):
    # Create a punch first
    _reset_active_signals()
    http.post(f"{API}/signals/tradingview", json={
        "secret": SECRET, "action": "BUY", "symbol": "MNQ1!", "interval": "1", "price": 29920.00,
    }, timeout=10)
    r = http.post(f"{API}/signals/tradingview", json={
        "secret": SECRET, "action": "CLOSE", "symbol": "MNQ1!",
    }, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "closed"
    assert d.get("expired", 0) >= 1


def test_duplicate_same_side_within_cooldown_returns_duplicate(http):
    _reset_active_signals()
    r1 = http.post(f"{API}/signals/tradingview", json={
        "secret": SECRET, "action": "BUY", "symbol": "MNQ1!", "interval": "1", "price": 29930.00,
    }, timeout=10)
    assert r1.status_code == 200 and r1.json()["status"] == "created"
    r2 = http.post(f"{API}/signals/tradingview", json={
        "secret": SECRET, "action": "BUY", "symbol": "MNQ1!", "interval": "1", "price": 29931.00,
    }, timeout=10)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate", r2.json()


# ---------- test-punch (PAPER) ----------
def test_test_punch_buy_creates_paper(http):
    _reset_active_signals()
    r = http.post(f"{API}/signals/test-punch", json={"side": "buy"}, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "created"
    assert d["side"] == "long"
    assert d.get("is_test") is True


def test_test_punch_sell_creates_paper(http):
    _reset_active_signals()
    r = http.post(f"{API}/signals/test-punch", json={"side": "sell"}, timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["status"] == "created"
    assert d["side"] == "short"
    assert d.get("is_test") is True


# ---------- Receiver status ----------
def test_receiver_status_structure(http):
    r = http.get(f"{API}/signals/receiver-status", timeout=10)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["webhook_url"].endswith("/api/signals/tradingview")
    assert d["secret_configured"] is True
    # After test-punches above, we should have inbound events
    assert d["receiver_live"] is True, f"receiver_live should be true after test punches: {d}"
    assert "alert_template" in d and "secret" in d["alert_template"]
    eng = d["engine"]
    for key in ("kill_switch", "cooldown_min", "cooldown_remaining_sec",
                "session_filter", "session_open", "now_et", "last_eval"):
        assert key in eng, f"engine missing {key}: {eng}"


# ---------- Session filter toggle ----------
def test_session_filter_toggles(http):
    r = http.post(f"{API}/signals/session-filter", json={"session_filter": False}, timeout=10)
    assert r.status_code == 200 and r.json()["session_filter"] is False
    r = http.post(f"{API}/signals/session-filter", json={"session_filter": True, "globex": False}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert d["session_filter"] is True
    assert d["globex"] is False


# ---------- Events log ----------
def test_events_newest_first(http):
    r = http.get(f"{API}/signals/events?limit=10", timeout=10)
    assert r.status_code == 200
    events = r.json()
    assert isinstance(events, list) and len(events) > 0
    timestamps = [e["ts"] for e in events]
    assert timestamps == sorted(timestamps, reverse=True), "events must be newest-first"


# ---------- Signal history has new fields ----------
def test_signals_have_new_fields(http):
    r = http.get(f"{API}/signals?limit=30", timeout=10)
    assert r.status_code == 200
    sigs = r.json()
    assert isinstance(sigs, list) and len(sigs) > 0
    # At least one signal from our test punches has the new schema fields
    tagged = [s for s in sigs if s.get("source") in ("test", "webhook", "live_engine")]
    assert tagged, "no punch-style signals present"
    sample = tagged[0]
    for f in ("interval", "note", "reason", "is_test"):
        assert f in sample, f"signal missing field {f}"


# ---------- stats / health / kill-switch still respond ----------
def test_stats_health_killswitch(http):
    for path in ("/signals/stats", "/signals/health"):
        r = http.get(f"{API}{path}", timeout=10)
        assert r.status_code == 200, f"{path} -> {r.status_code}"
    r = http.get(f"{API}/signals/kill-switch", timeout=10)
    assert r.status_code == 200
    assert r.json()["kill_switch"] is False


# ---------- Backend log check ----------
def test_backend_log_no_pipeline_exceptions():
    time.sleep(1)
    import subprocess
    out = subprocess.run(
        ["tail", "-n", "500", "/var/log/supervisor/backend.err.log"],
        capture_output=True, text=True,
    )
    log = out.stdout + out.stderr
    bad_signatures = [
        "signal_resolver_loop", "live_signal_engine_loop",
    ]
    hits = []
    for sig in bad_signatures:
        # Look for "Exception in" or "Traceback" within 5 lines of the signature
        idx = 0
        while True:
            idx = log.find(sig, idx)
            if idx == -1:
                break
            window = log[max(0, idx - 200): idx + 400]
            if "Traceback" in window or "Exception" in window and "handled" not in window.lower():
                hits.append(window[-300:])
            idx += 1
    assert not hits, f"Unhandled exceptions found near pipeline loops:\n{hits[0]}"
