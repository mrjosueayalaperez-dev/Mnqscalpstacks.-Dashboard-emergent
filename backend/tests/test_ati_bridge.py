"""Regression tests for the NinjaTrader ATI bridge (Phase 2 routing).

Follows the suite convention: sync httpx against the running server.
"""
import os
import sys
import time

import httpx

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bridge_template import build_oif_line  # noqa: E402

BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
API = f"{BASE}/api"


def _reset():
    httpx.post(f"{API}/operator/control/unkill", timeout=10)
    httpx.post(f"{API}/operator/control/resume", timeout=10)
    httpx.post(f"{API}/operator/control/reset_session", timeout=10)


def _set_ati(enabled: bool):
    r = httpx.post(f"{API}/ati/config", json={"enabled": enabled}, timeout=10)
    assert r.status_code == 200
    return r.json()


def test_ati_status_shape():
    r = httpx.get(f"{API}/ati/status", timeout=10)
    assert r.status_code == 200
    body = r.json()
    for key in ("enabled", "account", "instrument", "atm_template",
                "bridge_online", "pending", "dispatched"):
        assert key in body, f"missing {key}"


def test_ati_config_heartbeat_and_connection_status():
    st = _set_ati(True)
    assert st["enabled"] is True

    hb = httpx.post(f"{API}/ati/heartbeat", timeout=10)
    assert hb.status_code == 200 and hb.json()["bridge_online"] is True

    status = httpx.get(f"{API}/ati/status", timeout=10).json()
    assert status["bridge_online"] is True

    # cockpit connection flips CONNECTED when armed + bridge alive
    op = httpx.get(f"{API}/operator/state", timeout=10).json()
    assert op["connection"]["status"] == "CONNECTED"
    assert op["connection"]["ati_enabled"] is True

    _set_ati(False)
    op = httpx.get(f"{API}/operator/state", timeout=10).json()
    assert op["connection"]["status"] == "DISCONNECTED"


def test_order_enqueues_place_command_when_armed():
    _reset()
    _set_ati(True)
    time.sleep(1.6)  # clear server cooldown
    r = httpx.post(f"{API}/operator/order", json={
        "action": "BUY", "qty": 1, "order_type": "MARKET",
        "preset": "SNIPE_1R", "sl_ticks": 40, "tp_ticks": 60,
    }, timeout=15)
    try:
        if r.status_code == 503:
            return  # live feed offline — fill impossible, skip silently
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ati"]["routed"] is True
        cid = body["ati"]["command_id"]

        cmds = httpx.get(f"{API}/ati/commands", timeout=10).json()["commands"]
        mine = [c for c in cmds if c["id"] == cid]
        assert mine, "enqueued command not returned by /ati/commands"
        assert mine[0]["command_type"] == "PLACE"
        assert mine[0]["action"] == "BUY"
        assert mine[0]["atm_strategy_name"] == "SNIPE_1R"

        ack = httpx.post(f"{API}/ati/ack", json={"command_ids": [cid]}, timeout=10)
        assert ack.json()["acked"] == 1
        remaining = httpx.get(f"{API}/ati/commands", timeout=10).json()["commands"]
        assert all(c["id"] != cid for c in remaining)
    finally:
        _set_ati(False)
        _reset()


def test_order_not_routed_when_disabled():
    _reset()
    _set_ati(False)
    time.sleep(1.6)
    r = httpx.post(f"{API}/operator/order",
                   json={"action": "BUY", "qty": 1, "order_type": "MARKET"}, timeout=15)
    if r.status_code == 503:
        return
    assert r.json()["ati"]["routed"] is False
    _reset()


def test_flatten_enqueues_flatteneverything_when_armed():
    _reset()
    _set_ati(True)
    try:
        httpx.post(f"{API}/operator/control/flatten", timeout=10)
        cmds = httpx.get(f"{API}/ati/commands", timeout=10).json()["commands"]
        flats = [c for c in cmds if c["command_type"] == "FLATTENEVERYTHING"]
        assert flats, "FLATTEN did not enqueue FLATTENEVERYTHING"
        httpx.post(f"{API}/ati/ack", json={"command_ids": [c["id"] for c in flats]}, timeout=10)
    finally:
        _set_ati(False)
        _reset()


def test_bridge_script_download():
    r = httpx.get(f"{API}/ati/bridge-script", timeout=10)
    assert r.status_code == 200
    assert "attachment" in r.headers.get("content-disposition", "")
    assert "PLACE;" in r.text and "incoming" in r.text


def test_oif_line_formats():
    place = build_oif_line({
        "command_type": "PLACE", "account": "Sim101", "instrument": "MNQ 03-26",
        "action": "BUY", "quantity": 2, "order_type": "LIMIT",
        "limit_price": 29800.25, "tif": "DAY", "atm_strategy_name": "SNIPE_2R",
    })
    # PLACE;<ACCOUNT>;<INSTRUMENT>;<ACTION>;<QTY>;<TYPE>;[LIMIT];[STOP];<TIF>;[OCO];[ID];[STRATEGY];[STRAT ID]
    assert place == "PLACE;Sim101;MNQ 03-26;BUY;2;LIMIT;29800.25;;DAY;;;SNIPE_2R;"
    assert place.count(";") == 12

    close = build_oif_line({"command_type": "CLOSEPOSITION", "account": "Sim101", "instrument": "MNQ 03-26"})
    assert close == "CLOSEPOSITION;Sim101;MNQ 03-26;;;;;;;;;;"

    flat = build_oif_line({"command_type": "FLATTENEVERYTHING"})
    assert flat == "FLATTENEVERYTHING;;;;;;;;;;"
