"""
Full verification of the TradingView webhook -> Discord signal delivery pipeline.
Covers: webhook receive, signal persistence, sell path, duplicate suppression,
kill switch, pinescript endpoint, and latency.

NOTE: We rely on the REAL Discord webhook configured server-side. To keep the
user's channel clean we only cause the backend to fire at most a handful of
signals (buy, sell, and a couple of latency signals). All test symbols use
prefix 'TESTMNQ' where possible; but the webhook path is hard-coded to accept
MNQ, so we vary price to bypass duplicate checks and label logs clearly.
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


@pytest.fixture(scope="module")
def http():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Webhook secret is now required (header or JSON body). Dummy default for local runs only.
    s.headers["X-Webhook-Secret"] = os.environ.get("SIGNAL_WEBHOOK_SECRET", "test-secret-dummy")
    # Reset any active signals so duplicate suppression doesn't block us
    try:
        import asyncio
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        mongo_url = os.environ["MONGO_URL"]
        db_name = os.environ["DB_NAME"]
        async def _reset():
            client = AsyncIOMotorClient(mongo_url)
            await client[db_name].signals.update_many(
                {"status": "active"}, {"$set": {"status": "closed_by_test"}}
            )
            client.close()
        asyncio.run(_reset())
    except Exception as e:
        print(f"warn: could not reset signals: {e}")
    yield s
    # Cleanup: ensure kill switch OFF at end
    try:
        s.post(f"{API}/signals/kill-switch", json={"enabled": False, "reason": "test cleanup"}, timeout=10)
    except Exception:
        pass


def _unique_price(base=29790.50):
    # Vary decimals to avoid duplicate suppression collisions
    return round(base + (uuid.uuid4().int % 1000) * 0.25, 2)


# ---------- BUY / receive ----------
def test_webhook_buy_returns_received(http):
    price = _unique_price(29790.50)
    t0 = time.perf_counter()
    r = http.post(f"{API}/webhook/tradingview", json={
        "type": "buy", "symbol": "MNQ", "price": str(price), "time": "2026-01-15T10:00:00Z"
    }, timeout=10)
    dt = time.perf_counter() - t0
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "received", data
    assert data["side"] == "long"
    assert "signal_id" in data
    assert dt < 2.0, f"latency too high: {dt:.3f}s"
    # stash for next test
    pytest.buy_signal_id = data["signal_id"]
    pytest.buy_price = price


def test_signal_appears_in_history(http):
    r = http.get(f"{API}/signals?limit=10", timeout=10)
    assert r.status_code == 200
    signals = r.json()
    assert isinstance(signals, list) and len(signals) > 0
    match = next((s for s in signals if s.get("id") == pytest.buy_signal_id), None)
    assert match is not None, f"buy signal {pytest.buy_signal_id} not persisted"
    assert match["source"] == "webhook"
    assert match["side"] == "long"
    assert match["entry_price"] == pytest.buy_price
    assert match["stop_loss"] == pytest.buy_price - 8
    assert match["tp1"] == pytest.buy_price + 10
    assert match["tp2"] == pytest.buy_price + 20


# ---------- SELL ----------
def test_webhook_sell_path(http):
    price = _unique_price(29850.75)
    r = http.post(f"{API}/webhook/tradingview", json={
        "type": "sell", "symbol": "MNQ", "price": str(price), "time": "2026-01-15T10:05:00Z"
    }, timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "received"
    assert data["side"] == "short"
    # Fetch and verify stop is ABOVE entry for short
    sigs = http.get(f"{API}/signals?limit=10", timeout=10).json()
    match = next((s for s in sigs if s.get("id") == data["signal_id"]), None)
    assert match is not None
    assert match["stop_loss"] == price + 8
    assert match["stop_loss"] > match["entry_price"]
    assert match["tp1"] == price - 10
    assert match["tp2"] == price - 20


# ---------- Duplicate suppression ----------
def _reset_active_signals():
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    async def _r():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        await client[os.environ["DB_NAME"]].signals.update_many(
            {"status": "active"}, {"$set": {"status": "closed_by_test"}}
        )
        client.close()
    asyncio.run(_r())


def test_duplicate_suppression(http):
    _reset_active_signals()
    price = _unique_price(29900.25)
    r1 = http.post(f"{API}/webhook/tradingview", json={
        "type": "buy", "symbol": "MNQ", "price": str(price), "time": "2026-01-15T10:10:00Z"
    }, timeout=10)
    assert r1.status_code == 200
    assert r1.json()["status"] == "received"
    # Immediate repeat (same side within 3 minutes) -> duplicate
    r2 = http.post(f"{API}/webhook/tradingview", json={
        "type": "buy", "symbol": "MNQ", "price": str(price + 1), "time": "2026-01-15T10:10:05Z"
    }, timeout=10)
    assert r2.status_code == 200
    assert r2.json()["status"] == "duplicate", r2.json()


# ---------- Kill switch ----------
def test_kill_switch_blocks_and_restores(http):
    # Enable
    r_on = http.post(f"{API}/signals/kill-switch", json={"enabled": True, "reason": "test"}, timeout=10)
    assert r_on.status_code == 200
    assert r_on.json()["kill_switch"] is True

    # Verify GET reflects state
    assert http.get(f"{API}/signals/kill-switch", timeout=10).json()["kill_switch"] is True

    # Webhook should be blocked
    r_block = http.post(f"{API}/webhook/tradingview", json={
        "type": "sell", "symbol": "MNQ", "price": "30000.00", "time": "2026-01-15T10:20:00Z"
    }, timeout=10)
    assert r_block.status_code == 200
    assert r_block.json()["status"] == "blocked", r_block.json()

    # Disable (MUST leave OFF)
    r_off = http.post(f"{API}/signals/kill-switch", json={"enabled": False, "reason": "test end"}, timeout=10)
    assert r_off.status_code == 200
    assert r_off.json()["kill_switch"] is False
    assert http.get(f"{API}/signals/kill-switch", timeout=10).json()["kill_switch"] is False


# ---------- Pinescript endpoint ----------
def test_pinescript_endpoint(http):
    r = http.get(f"{API}/signals/pinescript", timeout=10)
    assert r.status_code == 200
    data = r.json()
    # Expect script text and webhook instructions
    script = data.get("pine_script") or data.get("pinescript") or data.get("script") or ""
    assert "alertcondition" in script, "Pine script missing alertcondition"
    assert '"type"' in script and '"buy"' in script and '"sell"' in script
    assert '"symbol"' in script
    instr = data.get("webhook_instructions", "") or data.get("instructions", "") or ""
    full_blob = str(data)
    assert "/api/webhook/tradingview" in full_blob
    # Should contain the derived host (https URL)
    assert "https://" in full_blob


# ---------- Latency ----------
def test_latency_average_under_2s(http):
    samples = []
    for i, (side, base) in enumerate([("buy", 31000.00), ("sell", 31100.00), ("buy", 31200.00)]):
        # ensure duplicates don't cause early return by alternating side + varying price
        price = _unique_price(base + i)
        t0 = time.perf_counter()
        r = http.post(f"{API}/webhook/tradingview", json={
            "type": side, "symbol": "MNQ", "price": str(price),
            "time": f"2026-01-15T11:{i:02d}:00Z"
        }, timeout=10)
        dt = time.perf_counter() - t0
        assert r.status_code == 200
        # accept received or duplicate (still exercised path)
        samples.append(dt)
    avg = sum(samples) / len(samples)
    print(f"latency samples={samples} avg={avg:.3f}s")
    assert avg < 2.0, f"avg latency {avg:.3f}s exceeds 2s"


# ---------- Discord delivery (indirect via logs) ----------
def test_discord_delivery_no_errors_in_backend_logs():
    """After the buy/sell/latency signals above, backend log must not contain 'Discord send failed'."""
    # Give background task a moment
    time.sleep(2)
    import subprocess
    out = subprocess.run(
        ["tail", "-n", "300", "/var/log/supervisor/backend.err.log"],
        capture_output=True, text=True
    )
    combined = out.stdout + out.stderr
    # Also check stdout log
    out2 = subprocess.run(
        ["tail", "-n", "300", "/var/log/supervisor/backend.out.log"],
        capture_output=True, text=True
    )
    combined += out2.stdout + out2.stderr
    assert "Discord send failed" not in combined, f"Discord failures found:\n{combined[-500:]}"
