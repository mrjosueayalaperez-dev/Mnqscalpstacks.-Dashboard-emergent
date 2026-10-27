"""Item 4 — TV_DATA_MODE drives labels; Yahoo is never real-time."""
import time

import pytest


@pytest.fixture()
def mf(monkeypatch):
    import market_feed
    monkeypatch.setitem(market_feed._last_tick, "source", "yahoo:NQ=F")
    monkeypatch.setitem(market_feed._last_tick, "price", 20000.0)
    monkeypatch.setitem(market_feed._live_override, "price", None)
    return market_feed


@pytest.mark.parametrize("mode", [None, "delayed", "realtime", "LIVE", ""])
def test_yahoo_always_delayed(mf, monkeypatch, mode):
    if mode is None:
        monkeypatch.delenv("TV_DATA_MODE", raising=False)
    else:
        monkeypatch.setenv("TV_DATA_MODE", mode)
    s = mf.get_last()
    assert s["data_mode"] == "delayed" and s["data_label"] == "DELAYED 10m"


@pytest.mark.parametrize("mode,label", [(None, "DELAYED 10m"), ("delayed", "DELAYED 10m"), ("bogus", "DELAYED 10m"), ("realtime", "REAL-TIME")])
def test_tradingview_tape_follows_flag(mf, monkeypatch, mode, label):
    if mode is None:
        monkeypatch.delenv("TV_DATA_MODE", raising=False)
    else:
        monkeypatch.setenv("TV_DATA_MODE", mode)
    monkeypatch.setitem(mf._live_override, "price", 20001.0)
    monkeypatch.setitem(mf._live_override, "ts", time.time())
    s = mf.get_last()
    assert s["source"] == "tradingview:live" and s["data_label"] == label


def test_data_mode_endpoint_default_delayed(client, monkeypatch):
    monkeypatch.delenv("TV_DATA_MODE", raising=False)
    r = client.get("/api/market/data-mode").json()
    assert r["tv_data_mode"] == "delayed" and r["yahoo_label"] == "DELAYED 10m"


def test_price_ingest_requires_header_secret(client):
    r = client.post("/api/signals/tradingview", content='{"action":"PRICE","price":20000}')
    assert r.status_code == 401
    r = client.post("/api/signals/tradingview", content='{"action":"PRICE","price":20000}', headers={"X-Webhook-Secret": "s" * 32})
    assert r.status_code == 200
