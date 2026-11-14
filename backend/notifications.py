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

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # pragma: no cover — zoneinfo is in the stdlib on 3.11+
    ET = timezone(timedelta(hours=-5))

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

DISCORD_EMBED_TITLE_LIMIT = 256
DISCORD_EMBED_DESC_LIMIT = 4000

# Statuses that occupy the dedup slot so a later tick or worker cannot re-send.
_OCCUPY_STATUSES = frozenset({"delivered", "pending", "uncertain"})

# HTTP codes where Discord almost certainly did not accept the message.
_RETRYABLE_HTTP = frozenset({408, 429, 500, 502, 503, 504})

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

    async def try_claim(
        self,
        *,
        alert_key: str,
        delivery_id: str,
        now: datetime,
        window_seconds: int,
        doc: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Atomically claim alert_key for this window.

        Returns the existing occupying row if the key is already claimed,
        or None if this caller now owns the slot (`doc` has been recorded as pending).
        """
        ...


class MemoryDeliveryStore:
    """In-memory store for unit tests (no Mongo, no network).

    Claims are taken under an asyncio lock so concurrent ticks cannot double-send.
    Rows are the source of truth, so a store rebuilt from the same rows behaves like
    a process that restarted and reloaded Mongo.
    """

    def __init__(self) -> None:
        self.rows: list[Dict[str, Any]] = []
        self._lock = asyncio.Lock()

    async def find_recent(self, alert_key: str, since_iso: str) -> Optional[Dict[str, Any]]:
        hits = [
            r for r in self.rows
            if r.get("alert_key") == alert_key
            and r.get("created_at", "") >= since_iso
            and r.get("status") in _OCCUPY_STATUSES
        ]
        return hits[-1] if hits else None

    async def record(self, doc: Dict[str, Any]) -> None:
        async with self._lock:
            self.rows.append(dict(doc))

    async def update(self, delivery_id: str, fields: Dict[str, Any]) -> None:
        async with self._lock:
            for r in self.rows:
                if r.get("id") == delivery_id:
                    r.update(fields)
                    return

    async def try_claim(
        self,
        *,
        alert_key: str,
        delivery_id: str,
        now: datetime,
        window_seconds: int,
        doc: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        async with self._lock:
            since = (now - timedelta(seconds=window_seconds)).isoformat()
            hits = [
                r for r in self.rows
                if r.get("alert_key") == alert_key
                and r.get("created_at", "") >= since
                and r.get("status") in _OCCUPY_STATUSES
            ]
            if hits:
                return hits[-1]
            self.rows.append(dict(doc))
            return None


class MongoDeliveryStore:
    """Persisted deliveries plus a unique-key claim collection that survives restart.

    `alert_delivery_claims._id` is the alert_key, so two workers cannot both insert
    a claim for the same key. Expired claims (outside the dedup window) are reused
    with a compare-and-set on `claimed_at`.
    """

    def __init__(self, db: Any) -> None:
        self._col = db.alert_deliveries
        self._dedup = db.alert_delivery_claims

    async def ensure_indexes(self) -> None:
        await self._col.create_index("id", unique=True)
        await self._col.create_index([("alert_key", 1), ("created_at", -1)])
        # _id on alert_delivery_claims is unique by default (the alert_key).

    async def find_recent(self, alert_key: str, since_iso: str) -> Optional[Dict[str, Any]]:
        return await self._col.find_one(
            {"alert_key": alert_key, "created_at": {"$gte": since_iso}, "status": {"$in": list(_OCCUPY_STATUSES)}},
            {"_id": 0},
            sort=[("created_at", -1)],
        )

    async def record(self, doc: Dict[str, Any]) -> None:
        await self._col.insert_one(dict(doc))

    async def update(self, delivery_id: str, fields: Dict[str, Any]) -> None:
        await self._col.update_one({"id": delivery_id}, {"$set": fields})

    def _parse_claimed_at(self, raw: Any, fallback: datetime) -> datetime:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return fallback
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt

    async def try_claim(
        self,
        *,
        alert_key: str,
        delivery_id: str,
        now: datetime,
        window_seconds: int,
        doc: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        now_iso = now.isoformat()
        since_iso = (now - timedelta(seconds=window_seconds)).isoformat()
        try:
            await self._dedup.insert_one({
                "_id": alert_key,
                "delivery_id": delivery_id,
                "claimed_at": now_iso,
            })
        except Exception as exc:  # DuplicateKeyError, or a shim that raises similarly
            if type(exc).__name__ not in {"DuplicateKeyError", "BulkWriteError"}:
                raise
            existing = await self._dedup.find_one({"_id": alert_key})
            if not existing:
                raise
            claimed_at_raw = existing.get("claimed_at")
            claimed_dt = self._parse_claimed_at(claimed_at_raw, now)
            if (now - claimed_dt).total_seconds() < window_seconds:
                prior = await self.find_recent(alert_key, since_iso)
                return prior or {
                    "id": existing.get("delivery_id"),
                    "alert_key": alert_key,
                    "status": "pending",
                }
            res = await self._dedup.update_one(
                {"_id": alert_key, "claimed_at": claimed_at_raw},
                {"$set": {"delivery_id": delivery_id, "claimed_at": now_iso}},
            )
            if getattr(res, "modified_count", 0) != 1:
                prior = await self.find_recent(alert_key, since_iso)
                return prior or {
                    "id": existing.get("delivery_id"),
                    "alert_key": alert_key,
                    "status": "pending",
                }
        await self._col.insert_one(dict(doc))
        return None


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


# ---- Alert labels -------------------------------------------------------------
# Nothing in this system places a trade; every body says so. Never "LIVE".

# Data-feed kinds (internal keys).
FEED_TRADINGVIEW = "tradingview"
FEED_DELAYED = "delayed"
FEED_TEST = "test"
FEED_PAPER = "paper"
FEED_SIMULATED = "simulated"
FEED_UNVERIFIED = "unverified"

# Founder-approved TradingView real-time title (Josue, Nov 13 2026 6:51 PM ET).
# The single place this wording lives.
TRADINGVIEW_TITLE_PREFIX = "REAL-TIME · alert"

# Title prefix per feed: "<prefix> · <DIRECTION> · <INSTRUMENT>".
TITLE_PREFIXES: Dict[str, str] = {
    FEED_TRADINGVIEW: TRADINGVIEW_TITLE_PREFIX,
    FEED_DELAYED: "DELAYED · practice alert",
    FEED_TEST: "TEST · practice alert",
    FEED_PAPER: "PAPER · practice alert",
    FEED_SIMULATED: "SIMULATED · practice alert",
    FEED_UNVERIFIED: "data source unverified · practice alert",
}

# Short data label for the "Data:" line in the body.
DATA_QUALIFIERS: Dict[str, str] = {
    FEED_TRADINGVIEW: "REAL-TIME (TradingView)",
    FEED_DELAYED: "DELAYED",
    FEED_TEST: "TEST",
    FEED_PAPER: "PAPER",
    FEED_SIMULATED: "SIMULATED",
    FEED_UNVERIFIED: "data source unverified",
}

# Stale-data guard windows (seconds since the alert's as_of timestamp).
# Yahoo is expected to be ~10 minutes behind, plus 5 minutes of grace.
# TradingView webhook alerts are stamped on arrival, so they get a tighter window.
TRADINGVIEW_STALE_MAX_AGE_SECONDS = 3 * 60
YAHOO_STALE_MAX_AGE_SECONDS = DEFAULT_YAHOO_DELAY_SECONDS + DEFAULT_STALE_GRACE_SECONDS

_TEST_SOURCES = {"test", "test-button", "test-punch"}
_SIM_SOURCES = {"demo", "sim", "simulated", "seed", "random"}
_YAHOO_SOURCES = {"live_engine", "legacy_ema_cross", "nq=f"}
_TV_SOURCES = {"webhook", "tradingview alert", "tradingview legacy webhook"}


def data_label_for_source(source: str, tv_data_mode: str = "") -> str:
    """Honest feed kind for a signal source. Unknown/empty is 'unverified', never TradingView.

    `tv_data_mode` is accepted for backward compatibility and ignored.
    """
    src = (source or "").strip().lower()
    if src.startswith("paper"):
        return FEED_PAPER
    if src in _TEST_SOURCES or src.startswith("test"):
        return FEED_TEST
    if src in _SIM_SOURCES:
        return FEED_SIMULATED
    if src.startswith("yahoo") or src in _YAHOO_SOURCES:
        return FEED_DELAYED
    if src in _TV_SOURCES or src.startswith("tradingview"):
        return FEED_TRADINGVIEW
    return FEED_UNVERIFIED


def normalize_feed_label(label: Optional[str]) -> str:
    """Map any legacy label value onto a feed kind. Unknown values are 'unverified'."""
    raw = (label or "").strip().lower()
    if raw in {"delayed", "delayed 10m", "yahoo"}:
        return FEED_DELAYED
    if raw in {"tradingview", "realtime", "real-time", "live"}:
        return FEED_TRADINGVIEW
    if raw == "test":
        return FEED_TEST
    if raw in {"paper", "paper-test"}:
        return FEED_PAPER
    if raw in {"simulated", "sim", "demo"}:
        return FEED_SIMULATED
    return FEED_UNVERIFIED


def signal_feed_label(signal: Dict[str, Any]) -> str:
    """Feed kind for a stored signal. Ignores the stored display label ('PAPER')."""
    if signal.get("is_test"):
        return FEED_TEST
    if signal.get("is_demo"):
        return FEED_SIMULATED
    return data_label_for_source(str(signal.get("source") or ""))


def data_qualifier(label: Optional[str]) -> str:
    return DATA_QUALIFIERS[normalize_feed_label(label)]


def title_prefix(label: Optional[str]) -> str:
    return TITLE_PREFIXES[normalize_feed_label(label)]


def stale_max_age_seconds(label: Optional[str]) -> int:
    if normalize_feed_label(label) == FEED_TRADINGVIEW:
        return TRADINGVIEW_STALE_MAX_AGE_SECONDS
    return YAHOO_STALE_MAX_AGE_SECONDS


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
    Timezone-aware values are compared in UTC; naive values are treated as UTC.
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


def parse_as_of(value: Any) -> Optional[datetime]:
    """Parse a payload timestamp. Invalid or missing values become None (stale)."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def format_alert_message(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Mobile-readable Discord embed. Never claims a trade was placed. Never says order flow.

    The delayed/paper/simulated/live label and the verbatim futures disclaimer are
    reserved and cannot be dropped by Discord's 4000-character embed cap. Only the
    trigger text is truncated if the body would overflow.
    """
    label_display = data_qualifier(payload.get("data_label"))
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
    trigger_out = trigger

    title = f"{title_prefix(payload.get('data_label'))} · {direction} · {instrument}"
    header = (
        f"This is an education/practice alert. No trade was placed.\n\n"
        f"**Time (ET):** {when}\n"
        f"**Instrument:** {instrument}\n"
        f"**Timeframe:** {timeframe}\n"
        f"**Direction:** {direction}\n"
        f"**Strategy:** {strategy}\n"
        f"**Trigger conditions:** "
    )
    data_line = f"**Data:** {label_display}"
    if payload.get("data_source"):
        data_line += f" ({payload['data_source']})"
    footer = "\n\n" + RISK_DISCLAIMER
    reserved = header + "\n" + data_line + footer
    budget = DISCORD_EMBED_DESC_LIMIT - len(reserved)
    if budget < 0:
        # Pathological header (huge instrument/strategy). Still keep the disclaimer
        # and data label; trim the header from the end before the reserved footer.
        keep = DISCORD_EMBED_DESC_LIMIT - len(footer) - len("\n" + data_line)
        header = (header[: max(0, keep - 3)] + "...") if keep > 3 else header[: max(0, keep)]
        trigger_out = ""
        description = header + "\n" + data_line + footer
        description = description[:DISCORD_EMBED_DESC_LIMIT]
        if RISK_DISCLAIMER not in description:
            description = description[: DISCORD_EMBED_DESC_LIMIT - len(footer)] + footer
    else:
        if len(trigger) > budget:
            cut = max(0, budget - 3)
            trigger_out = trigger[:cut] + "..."
        else:
            trigger_out = trigger
        description = header + trigger_out + "\n" + data_line + footer

    color = {"LONG": 5763719, "SHORT": 15548997, "WAIT": 9807270}.get(direction, 9807270)
    return {
        "username": "MNQ SCALP STACKS BOT",
        "embeds": [{
            "title": title[:DISCORD_EMBED_TITLE_LIMIT],
            "description": description[:DISCORD_EMBED_DESC_LIMIT],
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
            f"Trigger conditions: {trigger_out if 'trigger_out' in locals() else trigger}\n"
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


def _safe_error(exc: BaseException) -> str:
    """Exception type only. Never str(exc): httpx embeds the request URL in the message."""
    return type(exc).__name__


def _send_outcome(exc: BaseException) -> str:
    """Classify a transport error.

    retryable: the request almost certainly never reached Discord (safe to retry).
    ambiguous: Discord may already have accepted the message (do not retry; would duplicate).
    """
    # Connect-level timeouts never delivered a request. Read/write timeouts might have.
    if isinstance(exc, httpx.ConnectTimeout):
        return "retryable"
    if isinstance(exc, getattr(httpx, "PoolTimeout", tuple())):
        return "retryable"
    if isinstance(exc, (httpx.ReadTimeout, httpx.WriteTimeout)):
        return "ambiguous"
    if isinstance(exc, httpx.TimeoutException):
        return "ambiguous"
    if isinstance(exc, httpx.ConnectError):
        return "retryable"
    name = type(exc).__name__
    if name in {"ConnectError", "ConnectionError", "ConnectTimeout", "PoolTimeout"}:
        return "retryable"
    if isinstance(exc, ConnectionError):
        return "retryable"
    # Unknown exceptions after a send may have been accepted. Fail closed against duplicates.
    return "ambiguous"


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

    as_of = parse_as_of(payload.get("as_of"))
    if is_stale(as_of, now=now, expected_delay_seconds=0,
                grace_seconds=stale_max_age_seconds(payload.get("data_label"))):
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

    body = format_alert_message(payload)
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
    prior = await store.try_claim(
        alert_key=key,
        delivery_id=delivery_id,
        now=now,
        window_seconds=_dedup_window_seconds(),
        doc=pending,
    )
    if prior:
        skip = {
            "id": delivery_id,
            "alert_key": key,
            "status": "skipped_duplicate",
            "created_at": now.isoformat(),
            "attempts": 0,
            "last_error": None,
            "duplicate_of": prior.get("id"),
        }
        await store.record(skip)
        logger.info("Discord delivery skipped: duplicate alert_key in window")
        return _result(status="skipped_duplicate", attempts=0, duplicate_of=prior.get("id"))

    retries, backoff_base = _retry_settings()
    _sleep = sleep or asyncio.sleep
    url = (webhook_url if webhook_url is not None else os.environ.get("DISCORD_WEBHOOK_URL", "")).strip()
    last_error = "unknown"
    for attempt in range(1, retries + 1):
        outcome = "retryable"
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
            if code not in _RETRYABLE_HTTP:
                break
        except Exception as exc:  # noqa: BLE001 — recorded, not swallowed silently
            last_error = _safe_error(exc)
            outcome = _send_outcome(exc)
            logger.warning("Discord delivery attempt %s failed: %s", attempt, last_error)
            if outcome == "ambiguous":
                await store.update(delivery_id, {
                    "status": "uncertain",
                    "attempts": attempt,
                    "last_error": last_error,
                    "failed_at": datetime.now(timezone.utc).isoformat(),
                })
                logger.error(
                    "Discord delivery uncertain after %s attempt(s) (%s); not retrying to avoid a duplicate",
                    attempt,
                    last_error,
                )
                return _result(status="uncertain", attempts=attempt, last_error=last_error)
        await store.update(delivery_id, {"status": "pending", "attempts": attempt, "last_error": last_error})
        if attempt < retries:
            await _sleep(backoff_base * (2 ** (attempt - 1)))

    final_attempts = attempt
    await store.update(delivery_id, {
        "status": "failed",
        "attempts": final_attempts,
        "last_error": last_error,
        "failed_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.error("Discord delivery failed after %s attempts (%s)", final_attempts, last_error)
    return _result(status="failed", attempts=final_attempts, last_error=last_error)
