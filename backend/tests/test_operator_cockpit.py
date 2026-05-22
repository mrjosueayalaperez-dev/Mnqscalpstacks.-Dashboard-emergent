"""Operator cockpit regression: state, candles, order safety, master controls."""
import os
import time
import httpx

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
API = f"{BASE}/api"


def _reset():
    httpx.post(f"{API}/operator/control/unkill", timeout=10)
    httpx.post(f"{API}/operator/control/resume", timeout=10)
    httpx.post(f"{API}/operator/control/reset_session", timeout=10)


def test_state_shape():
    _reset()
    r = httpx.get(f"{API}/operator/state", timeout=10)
    assert r.status_code == 200
    s = r.json()
    for k in ("connection", "balance", "daily_pnl", "daily_trades", "max_daily_loss",
             "max_daily_trades", "automation_paused", "kill_switch", "position",
             "session_seconds", "market_open", "cooldown_ms_remaining"):
        assert k in s, f"missing {k}"


def test_candles_have_indicators():
    r = httpx.get(f"{API}/operator/candles", params={"timeframe": "5m", "count": 30}, timeout=10)
    assert r.status_code == 200
    d = r.json()
    assert len(d["candles"]) == 30
    assert len(d["ema21"]) >= 1  # 30 candles is enough for ema21
    assert len(d["vwap"]) == 30
    assert d["last_close"] is not None
    # OHLC sanity
    c = d["candles"][0]
    assert c["high"] >= max(c["open"], c["close"])
    assert c["low"] <= min(c["open"], c["close"])


def test_order_flow_buy_then_close():
    _reset()
    r1 = httpx.post(f"{API}/operator/order",
                    json={"action": "BUY", "symbol": "MNQ", "qty": 1, "order_type": "MARKET"},
                    timeout=10)
    assert r1.status_code == 200
    assert r1.json()["state"]["side"] == "LONG"

    # Immediate retry — cooldown
    r2 = httpx.post(f"{API}/operator/order",
                    json={"action": "BUY", "symbol": "MNQ", "qty": 1, "order_type": "MARKET"},
                    timeout=10)
    assert r2.status_code == 429

    time.sleep(1.7)
    r3 = httpx.post(f"{API}/operator/order",
                    json={"action": "CLOSE_LONG", "symbol": "MNQ", "qty": 1, "order_type": "MARKET"},
                    timeout=10)
    assert r3.status_code == 200
    assert r3.json()["state"]["side"] is None


def test_kill_switch_blocks_orders():
    _reset()
    httpx.post(f"{API}/operator/control/kill", timeout=10)
    r = httpx.post(f"{API}/operator/order",
                   json={"action": "BUY", "symbol": "MNQ", "qty": 1, "order_type": "MARKET"},
                   timeout=10)
    assert r.status_code == 423
    httpx.post(f"{API}/operator/control/unkill", timeout=10)


def test_master_controls():
    _reset()
    for act, key in [("pause", "automation_paused"),
                     ("resume", "automation_paused"),
                     ("kill", "kill_switch"),
                     ("unkill", "kill_switch"),
                     ("flatten", "position"),
                     ("reset_session", "action")]:
        r = httpx.post(f"{API}/operator/control/{act}", timeout=10)
        assert r.status_code == 200, f"{act} failed: {r.text}"
        assert r.json()["ok"] is True

    bad = httpx.post(f"{API}/operator/control/nonsense", timeout=10)
    assert bad.status_code == 400


def test_limit_requires_price():
    _reset()
    time.sleep(1.7)
    r = httpx.post(f"{API}/operator/order",
                   json={"action": "BUY", "symbol": "MNQ", "qty": 1, "order_type": "LIMIT"},
                   timeout=10)
    assert r.status_code == 400


def test_journal_writes():
    _reset()
    httpx.post(f"{API}/operator/order",
               json={"action": "BUY", "symbol": "MNQ", "qty": 1, "order_type": "MARKET"},
               timeout=10)
    r = httpx.get(f"{API}/operator/journal", params={"limit": 5}, timeout=10)
    assert r.status_code == 200
    entries = r.json()["entries"]
    assert len(entries) >= 1
    assert entries[0]["action"] in ("BUY", "FLATTEN_ALL", "CLOSE_LONG")
