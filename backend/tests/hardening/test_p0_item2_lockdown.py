"""Item 2 — fail-closed write key, header-only webhook secret, no broker routing."""
import asyncio
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
GOOD = {"X-API-Key": "k" * 32}
SEC = "s" * 32
HOLD = json.dumps({"action": "HOLD", "symbol": "MNQ1!"})


@pytest.fixture(autouse=True)
def _reset_operator(srv):
    srv._operator_state.update({"kill_switch": False, "daily_trades": 0, "daily_pnl": 0.0, "last_order_at": 0.0})


# ---- write key ----
@pytest.mark.parametrize("hdr", [{}, {"X-API-Key": ""}, {"X-API-Key": "wrong"}, {"X-API-Key": "k" * 31}])
def test_write_key_missing_or_wrong_401(client, hdr):
    assert client.post("/api/operator/control/pause", headers=hdr).status_code == 401


def test_write_key_env_unset_fails_closed(client, srv, monkeypatch):
    monkeypatch.setattr(srv, "RETOOL_API_KEY", "")
    assert client.post("/api/operator/control/pause").status_code == 503
    assert client.post("/api/operator/control/pause", headers={"X-API-Key": ""}).status_code == 503
    assert client.post("/api/operator/control/pause", headers=GOOD).status_code == 503


def test_write_key_good(client):
    assert client.post("/api/operator/control/pause", headers=GOOD).status_code == 200


def test_constant_time_compare_used():
    src = (ROOT / "backend" / "server.py").read_text()
    assert src.count("hmac.compare_digest(") >= 2


# ---- webhooks ----
@pytest.mark.parametrize("path", ["/api/signals/tradingview", "/api/webhook/tradingview"])
@pytest.mark.parametrize("kw", [
    {},                                                  # missing
    {"headers": {"X-Webhook-Secret": "nope"}},           # wrong
    {"params": {"secret": SEC}},                         # query param no longer accepted
])
def test_webhook_rejects(client, path, kw):
    body = HOLD if "signals" in path else json.dumps({"type": "buy", "price": "100"})
    r = client.post(path, content=body, **kw)
    assert r.status_code in (401, 403), r.text


def test_webhook_body_secret_not_accepted(client):
    r = client.post("/api/signals/tradingview", content=json.dumps({"action": "HOLD", "secret": SEC}))
    assert r.status_code == 401


@pytest.mark.parametrize("path", ["/api/signals/tradingview", "/api/webhook/tradingview"])
def test_webhook_secret_unset_rejected(client, srv, monkeypatch, path):
    monkeypatch.setattr(srv, "SIGNAL_WEBHOOK_SECRET", "")
    r = client.post(path, content=HOLD, headers={"X-Webhook-Secret": ""})
    assert r.status_code in (401, 403, 503)


def test_webhook_header_secret_ok(client):
    r = client.post("/api/signals/tradingview", content=HOLD, headers={"X-Webhook-Secret": SEC})
    assert r.status_code == 200


def test_receiver_status_never_leaks_secret(client):
    r = client.get("/api/signals/receiver-status")
    assert SEC not in r.text


# ---- ATI / NinjaTrader ----
def test_ati_config_gone(client):
    assert client.post("/api/ati/config", json={"enabled": True}, headers=GOOD).status_code in (403, 404, 405)
    assert client.get("/api/operator/state").json()["connection"]["ati_enabled"] is False


def test_ati_hard_disabled_even_if_state_flipped(srv):
    import ati
    ati._ati_state["enabled"] = True
    try:
        assert ati.ati_enabled() is False
        assert asyncio.get_event_loop().run_until_complete(ati.enqueue(srv._test_db, {"id": "x"})) is None
    finally:
        ati._ati_state["enabled"] = False


def test_operator_order_and_flatten_never_enqueue(client, srv):
    r = client.post("/api/operator/order", headers=GOOD,
                    json={"action": "BUY", "qty": 1, "order_type": "LIMIT", "limit_price": 20000.0})
    assert r.status_code == 200, r.text
    assert r.json()["ati"]["routed"] is False
    assert client.post("/api/operator/control/flatten", headers=GOOD).status_code == 200
    assert client.post("/api/operator/control/kill", headers=GOOD).status_code == 200
    n = asyncio.get_event_loop().run_until_complete(srv._test_db.ati_commands.count_documents({}))
    assert n == 0


def test_no_enqueue_call_sites():
    src = (ROOT / "backend" / "server.py").read_text()
    assert "ati.enqueue" not in src and "ati_commands.insert" not in src
