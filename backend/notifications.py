"""Reliable Discord delivery for practice alerts.

Never logs or returns the webhook URL. Never implies a broker order was placed.
Yahoo Finance data is always labeled delayed.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional, Protocol

import httpx

logger = logging.getLogger(__name__)

ET = timezone(timedelta(hours=-5))  # America/New_York is UTC-5 on this date (EST)

RISK_DISCLAIMER = (
    "Futures trading involves substantial risk of loss and is not suitable for all investors. "
    "This is education and structured practice, not financial advice. "
    "Past performance is not indicative of future results."
)

# Known non-values. Compared as exact trimmed strings; never printed.
_PLACEHOLDER_URLS = frozenset({
    "",
    "REPLACE_WITH_YOUR_DISCORD_WEBHOOK_URL",
    "YOUR_WEBHOOK_URL",
    "changeme",
})

# Yahoo tape is delayed ~10 minutes; "stale" means older than that expected delay plus a grace window.
DEFAULT_YAHOO_DELAY_SECONDS = 10 * 60
DEFAULT_STALE_GRACE_SECONDS = 5 * 60
DEFAULT_DEDUP_WINDOW_SECONDS = 3 * 60
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_BASE_SECONDS = 0.5

HttpPost = Callable[[str, Dict[str, Any]], Awaitable["HttpResult"]]


class HttpResult(Protocol):
    status_code: int


class DeliveryStore(Protocol):
    async def find_recent(self, alert_key: str, since_iso: str) -> Optional[Dict[str, Any]]:
        ...

    async def record(self, doc: Dict[str, Any]) -> None:
        ...

    async def update(self, delivery_id: str, fields: Dict[str, Any]) -> None:
        ...


class MemoryDeliveryStore:
    """In-memory store for unit tests (no Mongo, no network)."""

    def __init__(self) -> None:
        self.rows: list[Dict[str, Any]] = []

    async def find_recent(self, alert_key: str, since_iso: str) -> Optional[Dict[str, Any]]:
        hits = [
            r for r in self.rows
            if r.get("alert_key") == alert_key
            and r.get("created_at", "") >= since_iso
            and r.get("status") in ("delivered", "pending")
        ]
        return hits[-1] if hits else None

    async def record(self, doc: Dict[str, Any]) -> None:
        self.rows.append(dict(doc))

    async def update(self, delivery_id: str, fields: Dict[str, Any]) -> None:
        for r in self.rows:
            if r.get("id") == delivery_id:
                r.update(fields)
                return


class MongoDeliveryStore:
    def __init__(self, db: Any) -> None:
        self._col = db.alert_deliveries

    async def find_recent(self, alert_key: str, since_iso: str) -> Optional[Dict[str, Any]]:
        return await self._col.find_one(
            {"alert_key": alert_key, "created_at": {"$gte": since_iso}, "status": {"$in": ["delivered", "pending"]}},
            {"_id": 0},
            sort=[("created_at", -1)],
        )

    async def record(self, doc: Dict[str, Any]) -> None:
        await self._col.insert_one(dict(doc))

    async def update(self, delivery_id: str, fields: Dict[str, Any]) -> None:
        await self._col.update_one({"id": delivery_id}, {"$set": fields})


def discord_webhook_configured(url: Optional[str] = None) -> bool:
    """True when a non-placeholder webhook is set. Never returns or logs the value."""
    raw = os.environ.get("DISCORD_WEBHOOK_URL", "") if url is None else url
    value = (raw or "").strip()
    if value in _PLACEHOLDER_URLS:
        return False
    return value.startswith("https://") or value.startswith("http://")


def discord_config_status() -> Dict[str, Any]:
    """Public status only — no URL, no preview, no length."""
    return {"discord_configured": discord_webhook_configured()}


def data_label_for_source(source: str, tv_data_mode: str = "delayed") -> str:
    """Honest label for the actual feed. Yahoo is always delayed. 'live' only if licensed TV real-time."""
    src = (source or "").strip().lower()
    if src in {"test", "paper", "test-button", "paper-test", "test-punch"} or src.startswith("paper"):
        return "paper"
    if src in {"demo", "sim", "simulated", "seed"}:
        return "simulated"
    if src.startswith("yahoo") or src in {"live_engine", "legacy_ema_cross", "nq=f"}:
        return "delayed"
    if src in {"tradingview:live", "tradingview"} and (tv_data_mode or "").lower() == "realtime":
        return "live"
    # TradingView webhook with default / delayed mode, or unknown
    return "delayed"


def et_timestamp(when: Optional[datetime] = None) -> str:
    dt = when or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ET).strftime("%Y-%m-%d %H:%M:%S ET")


def make_alert_key(
    *,
    strategy: str,
    instrument: str,
    timeframe: str,
    direction: str,
    trigger: str,
) -> str:
    raw = "|".join([
        (strategy or "").strip().lower(),
        (instrument or "").strip().upper(),
        (timeframe or "").strip().lower(),
        (direction or "").strip().lower(),
        (trigger or "").strip().lower(),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def is_stale(
    as_of: Optional[datetime],
    *,
    now: Optional[datetime] = None,
    expected_delay_seconds: int = DEFAULT_YAHOO_DELAY_SECONDS,
    grace_seconds: int = DEFAULT_STALE_GRACE_SECONDS,
) -> bool:
    """True when the quote is older than the expected feed delay plus a grace window.

    Yahoo's ~10 minute delay is expected and is not, by itself, stale.
    Missing timestamps are treated as stale (fail closed).
    """
    if as_of is None:
        return True
    now = now or datetime.now(timezone.utc)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    max_age = expected_delay_seconds + grace_seconds
    return (now - as_of).total_seconds() > max_age


def format_alert_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Mobile-readable Discord embed. Never claims a trade was placed. Never says order flow."""
    label = (payload.get("data_label") or "delayed").lower()
    label_display = {
        "delayed": "DELAYED",
        "simulated": "SIMULATED",
        "paper": "PAPER",
        "live": "LIVE",
    }.get(label, label.upper())
    strategy = payload.get("strategy") or "unspecified"
    direction = (payload.get("direction") or "WAIT").upper()
    instrument = payload.get("instrument") or "MNQ"
    timeframe = payload.get("timeframe") or "n/a"
    trigger = payload.get("trigger") or "n/a"
    when = payload.get("timestamp_et") or et_timestamp()
    # Guard against leftover wording
    if "order flow" in trigger.lower() or "order-flow" in trigger.lower():
        trigger = trigger.replace("order flow", "candle delta").replace("order-flow", "candle-delta")
        trigger += " (candle range/delta only — not exchange bid/ask order-flow data)"

    title = f"{label_display} · practice alert · {direction} · {instrument}"
    description = (
        f"This is an education/practice alert. No trade was placed.\n\n"
        f"**Time (ET):** {when}\n"
        f"**Instrument:** {instrument}\n"
        f"**Timeframe:** {timeframe}\n"
        f"**Direction:** {direction}\n"
        f"**Strategy:** {strategy}\n"
        f"**Trigger conditions:** {trigger}\n"
        f"**Data:** {label_display}"
        + (f" ({payload['data_source']})" if payload.get("data_source") else "")
        + "\n\n"
        + RISK_DISCLAIMER
    )
    color = {"LONG": 5763719, "SHORT": 15548997, "WAIT": 9807270}.get(direction, 9807270)
    return {
        "username": "MNQ SCALP STACKS BOT",
        "embeds": [{
            "title": title[:256],
            "description": description[:4000],
            "color": color,
            "footer": {"text": "Education/practice only · no order was placed"},
        }],
        # Plain-text twin for logs/tests (no webhook URL)
        "text": (
            f"{title}\n"
            f"Time (ET): {when}\n"
            f"Instrument: {instrument}\n"
            f"Timeframe: {timeframe}\n"
            f"Direction: {direction}\n"
            f"Strategy: {strategy}\n"
            f"Trigger conditions: {trigger}\n"
            f"Data: {label_display}\n"
            f"No trade was placed.\n"
            f"{RISK_DISCLAIMER}"
        ),
    }


def _dedup_window_seconds() -> int:
    try:
        return int(os.environ.get("ALERT_DEDUP_WINDOW_SECONDS", DEFAULT_DEDUP_WINDOW_SECONDS))
    except ValueError:
        return DEFAULT_DEDUP_WINDOW_SECONDS


def _retry_settings() -> tuple[int, float]:
    try:
        retries = int(os.environ.get("ALERT_DISCORD_RETRIES", DEFAULT_RETRIES))
    except ValueError:
        retries = DEFAULT_RETRIES
    try:
        base = float(os.environ.get("ALERT_DISCORD_BACKOFF_BASE_SECONDS", DEFAULT_BACKOFF_BASE_SECONDS))
    except ValueError:
        base = DEFAULT_BACKOFF_BASE_SECONDS
    return max(1, retries), max(0.0, base)


async def deliver_discord(
    payload: Dict[str, Any],
    *,
    store: DeliveryStore,
    webhook_url: Optional[str] = None,
    http_post: Optional[HttpPost] = None,
    now: Optional[datetime] = None,
    sleep: Optional[Callable[[float], Awaitable[None]]] = None,
) -> Dict[str, Any]:
    """Send one practice alert to Discord with stale-guard, dedup, retry, and persisted status.

    `webhook_url` is accepted for tests only (a fake URL). Production callers should leave it
    unset so the env var is read inside this function and never returned.
    """
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delivery_id = str(uuid.uuid4())
    key = payload.get("alert_key") or make_alert_key(
        strategy=str(payload.get("strategy") or ""),
        instrument=str(payload.get("instrument") or ""),
        timeframe=str(payload.get("timeframe") or ""),
        direction=str(payload.get("direction") or ""),
        trigger=str(payload.get("trigger") or ""),
    )

    def _result(**extra: Any) -> Dict[str, Any]:
        base = {"id": delivery_id, "alert_key": key, "discord_configured": discord_webhook_configured(webhook_url)}
        base.update(extra)
        return base

    if not discord_webhook_configured(webhook_url):
        doc = {
            "id": delivery_id,
            "alert_key": key,
            "status": "skipped_unconfigured",
            "created_at": now.isoformat(),
            "attempts": 0,
            "last_error": None,
        }
        await store.record(doc)
        logger.info("Discord delivery skipped: webhook not configured")
        return _result(status="skipped_unconfigured", attempts=0)

    as_of = payload.get("as_of")
    if isinstance(as_of, str):
        try:
            as_of = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
        except ValueError:
            as_of = None
    if is_stale(as_of, now=now):
        doc = {
            "id": delivery_id,
            "alert_key": key,
            "status": "skipped_stale",
            "created_at": now.isoformat(),
            "attempts": 0,
            "last_error": "stale_data_guard",
        }
        await store.record(doc)
        logger.warning("Discord delivery skipped: stale data guard")
        return _result(status="skipped_stale", attempts=0)

    since = (now - timedelta(seconds=_dedup_window_seconds())).isoformat()
    prior = await store.find_recent(key, since)
    if prior:
        doc = {
            "id": delivery_id,
            "alert_key": key,
            "status": "skipped_duplicate",
            "created_at": now.isoformat(),
            "attempts": 0,
            "last_error": None,
            "duplicate_of": prior.get("id"),
        }
        await store.record(doc)
        logger.info("Discord delivery skipped: duplicate alert_key in window")
        return _result(status="skipped_duplicate", attempts=0, duplicate_of=prior.get("id"))

    body = format_alert_message(payload)
    # Do not persist the outbound JSON? Fine to persist title/status only.
    pending = {
        "id": delivery_id,
        "alert_key": key,
        "status": "pending",
        "created_at": now.isoformat(),
        "attempts": 0,
        "last_error": None,
        "strategy": payload.get("strategy"),
        "instrument": payload.get("instrument"),
        "direction": payload.get("direction"),
        "data_label": payload.get("data_label"),
    }
    await store.record(pending)

    retries, backoff_base = _retry_settings()
    _sleep = sleep or asyncio.sleep
    url = (webhook_url if webhook_url is not None else os.environ.get("DISCORD_WEBHOOK_URL", "")).strip()
    last_error = "unknown"
    for attempt in range(1, retries + 1):
        try:
            if http_post is not None:
                resp = await http_post(url, body)
                code = getattr(resp, "status_code", 0)
            else:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.post(url, json={k: body[k] for k in ("username", "embeds")}, timeout=8.0)
                    code = resp.status_code
            if code in (200, 204):
                await store.update(delivery_id, {
                    "status": "delivered",
                    "attempts": attempt,
                    "last_error": None,
                    "delivered_at": datetime.now(timezone.utc).isoformat(),
                })
                return _result(status="delivered", attempts=attempt)
            last_error = f"http_{code}"
        except Exception as exc:  # noqa: BLE001 — recorded, not swallowed silently
            last_error = type(exc).__name__
            logger.warning("Discord delivery attempt %s failed: %s", attempt, type(exc).__name__)
        await store.update(delivery_id, {"status": "pending", "attempts": attempt, "last_error": last_error})
        if attempt < retries:
            await _sleep(backoff_base * (2 ** (attempt - 1)))

    await store.update(delivery_id, {
        "status": "failed",
        "attempts": retries,
        "last_error": last_error,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.error("Discord delivery failed after %s attempts (%s)", retries, last_error)
    return _result(status="failed", attempts=retries, last_error=last_error)
