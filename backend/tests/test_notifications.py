"""Unit tests for reliable Discord delivery. No network, no real webhook, no secrets."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

import notifications as n


class _FakeResp:
    def __init__(self, code: int) -> None:
        self.status_code = code


@pytest.fixture
def store() -> n.MemoryDeliveryStore:
    return n.MemoryDeliveryStore()


def test_discord_config_status_never_includes_url(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/webhook/UNITTEST_NOT_A_SECRET")
    status = n.discord_config_status()
    assert status == {"discord_configured": True}
    assert "url" not in status
    assert "webhook" not in {k.lower() for k in status}
    dumped = str(status)
    assert "example.invalid" not in dumped
    assert "UNITTEST" not in dumped


def test_placeholder_and_empty_are_not_configured(monkeypatch):
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "")
    assert n.discord_webhook_configured() is False
    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "REPLACE_WITH_YOUR_DISCORD_WEBHOOK_URL")
    assert n.discord_webhook_configured() is False
    assert n.discord_config_status()["discord_configured"] is False


@pytest.mark.parametrize(
    "source,mode,expected",
    [
        ("yahoo:NQ=F", "delayed", "delayed"),
        ("live_engine", "delayed", "delayed"),
        ("test", "delayed", "paper"),
        ("paper-test", "delayed", "paper"),
        ("demo", "delayed", "simulated"),
        ("tradingview:live", "delayed", "delayed"),
        ("tradingview:live", "realtime", "live"),
        ("unknown", "delayed", "delayed"),
    ],
)
def test_data_label_is_honest(source, mode, expected):
    assert n.data_label_for_source(source, mode) == expected


def test_format_message_has_required_fields_and_disclaimer():
    body = n.format_alert_message({
        "strategy": "A Six Gates",
        "instrument": "MNQ",
        "timeframe": "15m confirmation / 5m bias / 1m entry",
        "direction": "LONG",
        "trigger": "G1–G6 pass; close >= VWAP",
        "data_label": "delayed",
        "data_source": "Yahoo NQ=F",
        "timestamp_et": "2026-11-13 18:00:00 ET",
    })
    text = body["text"]
    assert "2026-11-13 18:00:00 ET" in text
    assert "Instrument: MNQ" in text
    assert "15m confirmation / 5m bias / 1m entry" in text
    assert "Direction: LONG" in text
    assert "A Six Gates" in text
    assert "G1–G6 pass" in text
    assert "DELAYED" in text
    assert "No trade was placed" in text
    assert n.RISK_DISCLAIMER in text
    assert "order flow" not in text.lower()
    assert "order was placed" in body["embeds"][0]["footer"]["text"].lower() or "no order" in body["embeds"][0]["footer"]["text"].lower()


def test_format_message_rewrites_order_flow_wording():
    body = n.format_alert_message({
        "strategy": "Alerts panel",
        "instrument": "MNQ",
        "timeframe": "1m",
        "direction": "WAIT",
        "trigger": "candle order flow imbalance",
        "data_label": "delayed",
    })
    assert "order flow" not in body["text"].lower()
    assert "candle delta" in body["text"].lower() or "candle-delta" in body["text"].lower()


def test_stale_guard_accounts_for_yahoo_delay():
    now = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    # 10 minutes old: expected Yahoo delay, not stale
    fresh = now - timedelta(minutes=10)
    assert n.is_stale(fresh, now=now) is False
    # 20 minutes old: delay + grace exceeded
    old = now - timedelta(minutes=20)
    assert n.is_stale(old, now=now) is True
    assert n.is_stale(None, now=now) is True


@pytest.mark.asyncio
async def test_skipped_when_unconfigured(store, monkeypatch):
    monkeypatch.delenv("DISCORD_WEBHOOK_URL", raising=False)
    result = await n.deliver_discord(
        {"strategy": "A Six Gates", "instrument": "MNQ", "direction": "LONG", "trigger": "t",
         "timeframe": "1m", "data_label": "delayed", "as_of": datetime.now(timezone.utc)},
        store=store,
        webhook_url="",
    )
    assert result["status"] == "skipped_unconfigured"
    assert result["discord_configured"] is False
    assert store.rows[-1]["status"] == "skipped_unconfigured"


@pytest.mark.asyncio
async def test_stale_payload_is_not_sent(store):
    calls = []

    async def post(url, body):
        calls.append(1)
        return _FakeResp(204)

    old = datetime.now(timezone.utc) - timedelta(minutes=30)
    result = await n.deliver_discord(
        {"strategy": "B Outer Range Extremes", "instrument": "MNQ", "direction": "SHORT",
         "trigger": "R3 engulfing", "timeframe": "15m", "data_label": "delayed", "as_of": old},
        store=store,
        webhook_url="https://example.invalid/hook",
        http_post=post,
    )
    assert result["status"] == "skipped_stale"
    assert calls == []
    assert store.rows[-1]["last_error"] == "stale_data_guard"


@pytest.mark.asyncio
async def test_retry_then_success_is_delivered(store, monkeypatch):
    monkeypatch.setenv("ALERT_DISCORD_RETRIES", "3")
    monkeypatch.setenv("ALERT_DISCORD_BACKOFF_BASE_SECONDS", "0.01")
    sleeps = []
    calls = []

    async def post(url, body):
        calls.append(url)
        if len(calls) < 3:
            raise ConnectionError("boom")
        return _FakeResp(204)

    async def sleeper(s):
        sleeps.append(s)

    now = datetime.now(timezone.utc)
    result = await n.deliver_discord(
        {"strategy": "Alerts panel (breakout)", "instrument": "MNQ", "direction": "LONG",
         "trigger": "price above 28000", "timeframe": "1m", "data_label": "delayed", "as_of": now},
        store=store,
        webhook_url="https://example.invalid/hook",
        http_post=post,
        sleep=sleeper,
        now=now,
    )
    assert result["status"] == "delivered"
    assert result["attempts"] == 3
    assert len(calls) == 3
    assert sleeps == [0.01, 0.02]
    row = next(r for r in store.rows if r["id"] == result["id"])
    assert row["status"] == "delivered"
    assert row["last_error"] is None
    # URL must not be persisted
    assert "example.invalid" not in str(row)


@pytest.mark.asyncio
async def test_persisted_failure_after_retries(store, monkeypatch):
    monkeypatch.setenv("ALERT_DISCORD_RETRIES", "2")
    monkeypatch.setenv("ALERT_DISCORD_BACKOFF_BASE_SECONDS", "0.01")

    async def post(url, body):
        return _FakeResp(500)

    async def sleeper(s):
        return None

    now = datetime.now(timezone.utc)
    result = await n.deliver_discord(
        {"strategy": "A Six Gates", "instrument": "MNQ", "direction": "SHORT",
         "trigger": "x", "timeframe": "1m", "data_label": "paper", "as_of": now},
        store=store,
        webhook_url="https://example.invalid/hook",
        http_post=post,
        sleep=sleeper,
        now=now,
    )
    assert result["status"] == "failed"
    assert result["attempts"] == 2
    assert result["last_error"] == "http_500"
    row = next(r for r in store.rows if r["id"] == result["id"])
    assert row["status"] == "failed"
    assert row["last_error"] == "http_500"


@pytest.mark.asyncio
async def test_dedup_same_alert_key_within_window(store, monkeypatch):
    monkeypatch.setenv("ALERT_DEDUP_WINDOW_SECONDS", "180")
    calls = []

    async def post(url, body):
        calls.append(1)
        return _FakeResp(204)

    now = datetime.now(timezone.utc)
    payload = {
        "strategy": "A Six Gates",
        "instrument": "MNQ",
        "direction": "LONG",
        "trigger": "G1 location",
        "timeframe": "1m",
        "data_label": "delayed",
        "as_of": now,
    }
    first = await n.deliver_discord(payload, store=store, webhook_url="https://example.invalid/hook",
                                    http_post=post, now=now)
    second = await n.deliver_discord(payload, store=store, webhook_url="https://example.invalid/hook",
                                     http_post=post, now=now + timedelta(seconds=30))
    assert first["status"] == "delivered"
    assert second["status"] == "skipped_duplicate"
    assert second["duplicate_of"] == first["id"]
    assert len(calls) == 1


def test_alert_key_is_stable_for_same_fields():
    a = n.make_alert_key(strategy="A Six Gates", instrument="MNQ", timeframe="1m",
                         direction="LONG", trigger="G1")
    b = n.make_alert_key(strategy="A Six Gates", instrument="mnq", timeframe="1m",
                         direction="long", trigger="g1")
    c = n.make_alert_key(strategy="B Outer Range Extremes", instrument="MNQ", timeframe="1m",
                         direction="LONG", trigger="G1")
    assert a == b
    assert a != c
