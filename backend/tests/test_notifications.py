"""Unit tests for reliable Discord delivery. No network, no real webhook, no secrets."""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
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


def test_stale_guard_missing_and_invalid_timestamps():
    now = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    assert n.is_stale(None, now=now) is True
    assert n.parse_as_of(None) is None
    assert n.parse_as_of("") is None
    assert n.parse_as_of("   ") is None
    assert n.parse_as_of("not-a-date") is None
    assert n.is_stale(n.parse_as_of("not-a-date"), now=now) is True


def test_stale_guard_timezone_aware_and_naive():
    now = datetime(2026, 11, 13, 23, 0, tzinfo=timezone.utc)
    # 10 minutes old in ET is the same instant as 10 minutes old in UTC
    as_of_et = datetime(2026, 11, 13, 17, 50, tzinfo=n.ET)  # 22:50 UTC
    assert n.is_stale(as_of_et, now=now) is False
    as_of_et_old = datetime(2026, 11, 13, 17, 0, tzinfo=n.ET)  # 22:00 UTC = 60 min
    assert n.is_stale(as_of_et_old, now=now) is True
    # Naive is treated as UTC (same clock as an aware UTC timestamp)
    naive_fresh = datetime(2026, 11, 13, 22, 50)  # interpreted as UTC
    assert n.is_stale(naive_fresh, now=now) is False
    naive_old = datetime(2026, 11, 13, 22, 0)
    assert n.is_stale(naive_old, now=now) is True
    # ISO string with Z
    parsed = n.parse_as_of("2026-11-13T22:50:00Z")
    assert n.is_stale(parsed, now=now) is False


@pytest.mark.asyncio
async def test_missing_as_of_is_not_sent(store):
    calls = []

    async def post(url, body):
        calls.append(1)
        return _FakeResp(204)

    result = await n.deliver_discord(
        {"strategy": "Alerts panel", "instrument": "MNQ", "direction": "LONG",
         "trigger": "price above 28000", "timeframe": "1m", "data_label": "delayed"},
        store=store,
        webhook_url="https://example.invalid/hook",
        http_post=post,
    )
    assert result["status"] == "skipped_stale"
    assert calls == []


def test_format_message_keeps_disclaimer_and_label_when_truncated():
    trigger = "G1 location " + ("x" * 5000)
    body = n.format_alert_message({
        "strategy": "Alerts panel (breakout)",
        "instrument": "MNQ",
        "timeframe": "1m",
        "direction": "LONG",
        "trigger": trigger,
        "data_label": "delayed",
        "data_source": "Yahoo NQ=F",
        "timestamp_et": "2026-11-13 18:00:00 ET",
    })
    desc = body["embeds"][0]["description"]
    assert len(desc) <= n.DISCORD_EMBED_DESC_LIMIT
    assert n.RISK_DISCLAIMER in desc
    assert desc.endswith(n.RISK_DISCLAIMER)
    assert "**Data:** DELAYED" in desc
    assert "DELAYED" in body["embeds"][0]["title"]
    assert n.RISK_DISCLAIMER in body["text"]


def test_safe_error_never_includes_url():
    req = httpx.Request("POST", "https://example.invalid/webhook/SECRETVALUE")
    exc = httpx.ConnectError("Failed to send request to https://example.invalid/webhook/SECRETVALUE", request=req)
    token = n._safe_error(exc)
    assert token == "ConnectError"
    assert "SECRETVALUE" not in token
    assert "example.invalid" not in token
    assert "https://" not in token


@pytest.mark.asyncio
async def test_exception_url_is_not_logged_or_persisted(store, caplog):
    import httpx as _httpx

    async def post(url, body):
        raise _httpx.ConnectError(
            "Failed to send request to https://example.invalid/webhook/SECRETVALUE",
            request=_httpx.Request("POST", "https://example.invalid/webhook/SECRETVALUE"),
        )

    async def sleeper(s):
        return None

    now = datetime.now(timezone.utc)
    with caplog.at_level(logging.WARNING):
        result = await n.deliver_discord(
            {"strategy": "A Six Gates", "instrument": "MNQ", "direction": "LONG",
             "trigger": "G1", "timeframe": "1m", "data_label": "delayed", "as_of": now},
            store=store,
            webhook_url="https://example.invalid/webhook/SECRETVALUE",
            http_post=post,
            sleep=sleeper,
            now=now,
        )
    blob = caplog.text + str(result) + str(store.rows)
    assert "SECRETVALUE" not in blob
    assert "example.invalid" not in blob
    assert result["last_error"] == "ConnectError"


@pytest.mark.asyncio
async def test_owner_alert_logs_do_not_include_webhook_url(monkeypatch, caplog):
    import notify

    monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://example.invalid/webhook/SECRETVALUE")

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            raise httpx.ConnectError(
                "Failed to send request to https://example.invalid/webhook/SECRETVALUE",
                request=httpx.Request("POST", "https://example.invalid/webhook/SECRETVALUE"),
            )

    monkeypatch.setattr(notify.httpx, "AsyncClient", FakeClient)
    with caplog.at_level(logging.WARNING):
        await notify._post({"content": "unit test"})
    assert "SECRETVALUE" not in caplog.text
    assert "example.invalid" not in caplog.text
    assert "ConnectError" in caplog.text


@pytest.mark.asyncio
async def test_timeout_after_send_is_not_retried(store, monkeypatch):
    monkeypatch.setenv("ALERT_DISCORD_RETRIES", "3")
    monkeypatch.setenv("ALERT_DISCORD_BACKOFF_BASE_SECONDS", "0.01")
    calls = []

    async def post(url, body):
        calls.append(1)
        raise httpx.ReadTimeout(
            "Read timeout",
            request=httpx.Request("POST", "https://example.invalid/webhook/SECRETVALUE"),
        )

    async def sleeper(s):
        raise AssertionError("must not backoff-retry after an ambiguous timeout")

    now = datetime.now(timezone.utc)
    payload = {
        "strategy": "A Six Gates",
        "instrument": "MNQ",
        "direction": "LONG",
        "trigger": "timeout-case",
        "timeframe": "1m",
        "data_label": "delayed",
        "as_of": now,
    }
    result = await n.deliver_discord(
        payload, store=store, webhook_url="https://example.invalid/hook",
        http_post=post, sleep=sleeper, now=now,
    )
    assert result["status"] == "uncertain"
    assert result["attempts"] == 1
    assert result["last_error"] == "ReadTimeout"
    assert len(calls) == 1
    row = next(r for r in store.rows if r["id"] == result["id"])
    assert row["status"] == "uncertain"
    assert "SECRETVALUE" not in str(row)
    # A later tick must not re-send (dedup occupies 'uncertain')
    second = await n.deliver_discord(
        payload, store=store, webhook_url="https://example.invalid/hook",
        http_post=post, now=now + timedelta(seconds=10),
    )
    assert second["status"] == "skipped_duplicate"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_connect_timeout_is_retried(store, monkeypatch):
    monkeypatch.setenv("ALERT_DISCORD_RETRIES", "3")
    monkeypatch.setenv("ALERT_DISCORD_BACKOFF_BASE_SECONDS", "0.01")
    calls = []

    async def post(url, body):
        calls.append(1)
        if len(calls) < 2:
            raise httpx.ConnectTimeout("connect timeout")
        return _FakeResp(204)

    sleeps = []

    async def sleeper(s):
        sleeps.append(s)

    now = datetime.now(timezone.utc)
    result = await n.deliver_discord(
        {"strategy": "A Six Gates", "instrument": "MNQ", "direction": "LONG",
         "trigger": "connect-timeout", "timeframe": "1m", "data_label": "delayed", "as_of": now},
        store=store, webhook_url="https://example.invalid/hook",
        http_post=post, sleep=sleeper, now=now,
    )
    assert result["status"] == "delivered"
    assert result["attempts"] == 2
    assert len(calls) == 2
    assert sleeps == [0.01]


@pytest.mark.asyncio
async def test_http_400_is_not_retried(store, monkeypatch):
    monkeypatch.setenv("ALERT_DISCORD_RETRIES", "3")
    calls = []

    async def post(url, body):
        calls.append(1)
        return _FakeResp(400)

    now = datetime.now(timezone.utc)
    result = await n.deliver_discord(
        {"strategy": "A Six Gates", "instrument": "MNQ", "direction": "LONG",
         "trigger": "bad-request", "timeframe": "1m", "data_label": "delayed", "as_of": now},
        store=store, webhook_url="https://example.invalid/hook",
        http_post=post, now=now,
    )
    assert result["status"] == "failed"
    assert result["attempts"] == 1
    assert result["last_error"] == "http_400"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_concurrent_ticks_only_one_delivery(store):
    started = asyncio.Event()
    release = asyncio.Event()
    calls = []

    async def post(url, body):
        calls.append(1)
        started.set()
        await release.wait()
        return _FakeResp(204)

    now = datetime.now(timezone.utc)
    payload = {
        "strategy": "A Six Gates",
        "instrument": "MNQ",
        "direction": "LONG",
        "trigger": "concurrent-tick",
        "timeframe": "1m",
        "data_label": "delayed",
        "as_of": now,
    }
    first_task = asyncio.create_task(n.deliver_discord(
        payload, store=store, webhook_url="https://example.invalid/hook",
        http_post=post, now=now,
    ))
    await started.wait()
    second_task = asyncio.create_task(n.deliver_discord(
        payload, store=store, webhook_url="https://example.invalid/hook",
        http_post=post, now=now,
    ))
    await asyncio.sleep(0.05)
    release.set()
    first, second = await asyncio.gather(first_task, second_task)
    statuses = {first["status"], second["status"]}
    assert statuses == {"delivered", "skipped_duplicate"}
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_dedup_state_survives_store_rebuild(monkeypatch):
    """Simulate a process restart by rebuilding the store from persisted rows."""
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
        "trigger": "restart-case",
        "timeframe": "1m",
        "data_label": "delayed",
        "as_of": now,
    }
    store = n.MemoryDeliveryStore()
    first = await n.deliver_discord(
        payload, store=store, webhook_url="https://example.invalid/hook",
        http_post=post, now=now,
    )
    assert first["status"] == "delivered"
    restarted = n.MemoryDeliveryStore()
    restarted.rows = [dict(r) for r in store.rows]
    second = await n.deliver_discord(
        payload, store=restarted, webhook_url="https://example.invalid/hook",
        http_post=post, now=now + timedelta(seconds=30),
    )
    assert second["status"] == "skipped_duplicate"
    assert len(calls) == 1
