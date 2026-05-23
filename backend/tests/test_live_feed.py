"""Live MNQ feed regression — REST snapshot + WebSocket stream."""
import asyncio
import os

import httpx
import pytest
import websockets

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
API = f"{BASE}/api"
WS = BASE.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws/mnq"


def test_rest_snapshot_is_live_not_synthetic():
    r = httpx.get(f"{API}/futures/mnq", timeout=15)
    assert r.status_code == 200
    d = r.json()
    # Price must be a sane MNQ value (>1000) and source must be the live feed
    assert d["price"] > 1000, f"price too low — feed not live? got {d['price']}"
    assert d.get("data_source", "").startswith("yahoo:"), d.get("data_source")
    assert d.get("is_mock") is False
    # Indicators present
    for k in ("vwap", "ema21", "high", "low", "previous_close"):
        assert d.get(k) is not None


def test_candles_use_real_feed():
    r = httpx.get(f"{API}/operator/candles", params={"timeframe": "5m", "count": 30}, timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert d["source"].startswith("yahoo:")
    assert len(d["candles"]) > 0
    # Last close in a sane MNQ range
    assert d["last_close"] > 1000


def test_order_fills_at_live_price_not_18500():
    httpx.post(f"{API}/operator/control/reset_session", timeout=10)
    # Sleep past the server-side 1500ms cooldown to avoid 429 collisions with other tests
    import time
    time.sleep(2)
    r = httpx.post(
        f"{API}/operator/order",
        json={"action": "BUY", "symbol": "MNQ", "qty": 1, "order_type": "MARKET"},
        timeout=15,
    )
    assert r.status_code == 200, f"unexpected status {r.status_code}: {r.text}"
    fill = r.json()["order"]["fill_price"]
    # Fill must reflect the live feed, not the old hardcoded 18500
    assert fill > 1000
    assert abs(fill - 18500) > 100, f"fill suspiciously close to old hardcoded 18500: {fill}"


@pytest.mark.asyncio
async def test_websocket_streams_ticks():
    async with websockets.connect(WS, open_timeout=15) as ws:
        msg = await asyncio.wait_for(ws.recv(), timeout=15)
        import json
        snap = json.loads(msg)
        assert "price" in snap and snap["price"] > 1000
        assert snap.get("source", "").startswith("yahoo:")
