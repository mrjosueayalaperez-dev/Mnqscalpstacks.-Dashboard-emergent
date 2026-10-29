"""TradingView ingest activities (paper-cut 2).

Display-only signals: these activities write signal docs + audit records and send the
Discord embed. They never touch ATI, /trades, or any order-routing code.
The webhook secret never reaches these activities (the API strips it before starting the workflow).
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, Optional
from zoneinfo import ZoneInfo

from temporalio import activity
from temporalio.exceptions import ApplicationError

ET = ZoneInfo("America/New_York")
SIGNAL_ACTIONS = ("BUY", "SELL", "CLOSE", "HOLD")

_db = None  # Motor database handle, set by the worker (or tests)
_indexes_ready = False
_discord_sender: Optional[Callable[[dict], Awaitable[bool]]] = None


def set_db(db) -> None:
    global _db, _indexes_ready
    _db = db
    _indexes_ready = False


def set_discord_sender(fn: Optional[Callable[[dict], Awaitable[bool]]]) -> None:
    global _discord_sender
    _discord_sender = fn


def _get_db():
    global _db
    if _db is None:
        from motor.motor_asyncio import AsyncIOMotorClient
        _db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ.get("DB_NAME", "mnqscalpstacks")]
    return _db


async def ensure_indexes(db=None) -> None:
    """Idempotent. sparse=True so pre-existing signals without ingest_key are unaffected."""
    global _indexes_ready
    db = db if db is not None else _get_db()
    if _indexes_ready:
        return
    try:
        await db.signals.create_index("ingest_key", unique=True, sparse=True, name="uniq_ingest_key")
        await db.signal_ingest_audit.create_index("workflow_id", unique=True, name="uniq_workflow_id")
    except Exception as e:  # never block ingest on an index problem; the upserts below stay idempotent
        if activity.in_activity():
            activity.logger.warning(f"ensure_indexes: {e}")
    _indexes_ready = True


async def _live_price() -> float:
    from market_feed import get_last, refresh_once  # delayed Yahoo feed (same as the API)
    return float(get_last().get("price") or (await refresh_once()).get("price") or 0)


@activity.defn
async def validate_and_price(p: Dict[str, Any]) -> Dict[str, Any]:
    action = str(p.get("action", "")).upper()
    if action not in SIGNAL_ACTIONS:
        raise ApplicationError(f"Unsupported action: {action}", 400, type="ValidationError", non_retryable=True)
    out = dict(p, action=action)
    if action in ("BUY", "SELL"):
        try:
            fp = float(p.get("price")) if p.get("price") else 0.0
        except (TypeError, ValueError):
            if p.get("route") == "legacy":
                raise ApplicationError("Invalid price in webhook payload", 400, type="ValidationError", non_retryable=True)
            fp = 0.0
        if not fp:
            fp = await _live_price()
            if not fp:
                detail = ("No price in payload and live feed unavailable" if p.get("route") == "legacy"
                          else "No price available")
                raise ApplicationError(detail, 422, type="ValidationError", non_retryable=True)
        out["price"] = float(fp)
    return out


def _signal_doc(p: Dict[str, Any], side: str, key: str) -> Dict[str, Any]:
    price = p["price"]
    legacy = p.get("route") == "legacy"
    r = (lambda x: x) if legacy else (lambda x: round(x, 2))
    stop = price - 8 if side == "long" else price + 8
    tp1 = price + 10 if side == "long" else price - 10
    tp2 = price + 20 if side == "long" else price - 20
    doc = {
        "id": str(uuid.uuid4()), "symbol": p.get("db_symbol", "MNQ"), "side": side,
        "entry_price": r(price), "stop_loss": r(stop), "tp1": r(tp1), "tp2": r(tp2),
        "confluence_score": 2, "components": {"webhook": True},
        "trend_direction": "bullish" if side == "long" else "bearish",
        "status": "active", "outcome": None, "pnl_points": None, "discord_sent": False,
        "source": "webhook", "created_at": datetime.now(timezone.utc).isoformat(),
        "ingest_key": key,
    }
    if not legacy:
        reason = f"{p.get('source', 'TradingView alert')} · {p.get('symbol', 'MNQ1!')} {p.get('interval', '1')}m"
        doc.update({"interval": p.get("interval", "1"), "confidence": 84, "note": p.get("note", ""),
                    "reason": reason, "is_test": False})
    return doc


def _body_for(p: Dict[str, Any], doc: Dict[str, Any]) -> Dict[str, Any]:
    if p.get("route") == "legacy":
        return {"status": "received", "signal_id": doc["id"], "side": doc["side"]}
    return {"status": "created", "signal_id": doc["id"], "side": doc["side"], "price": p["price"], "is_test": False}


async def _is_cooldown_dup(db, symbol: str, side: str, minutes: int) -> bool:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    return await db.signals.find_one({"symbol": symbol, "side": side, "created_at": {"$gte": cutoff},
                                     "status": "active"}) is not None


@activity.defn
async def persist_signal(p: Dict[str, Any]) -> Dict[str, Any]:
    """Idempotent per ingest_key (= workflow id). Re-runs return the first stored result."""
    db = _get_db()
    await ensure_indexes(db)
    key = p["ingest_key"]
    cached = await db.signal_ingest_audit.find_one({"workflow_id": key, "persist_result": {"$exists": True}})
    if cached:
        return cached["persist_result"]

    action = p["action"]
    legacy = p.get("route") == "legacy"
    if action == "HOLD":
        note = p.get("note") or "HOLD — waiting for confirmation"
        await db.signals.update_one({"ingest_key": key}, {"$setOnInsert": {
            "id": str(uuid.uuid4()), "symbol": "MNQ", "side": "hold", "status": "held", "action": "HOLD",
            "executed": False, "source": p.get("source", "TradingView alert"), "interval": "1", "note": note,
            "reason": note, "is_test": False, "created_at": datetime.now(timezone.utc).isoformat(),
            "ingest_key": key}}, upsert=True)
        res = {"result": "held", "notify": False, "signal_id": None,
               "body": {"ok": True, "action": "HOLD", "executed": False, "status": "held",
                        "message": "HOLD accepted — no order placed."},
               "event": (True, "HOLD accepted — no trade placed.")}
    elif action == "CLOSE":
        r = await db.signals.update_many({"status": "active"}, {"$set": {"status": "expired"}})
        res = {"result": "closed", "notify": False, "signal_id": None,
               "body": {"status": "closed", "expired": r.modified_count},
               "event": (True, f"CLOSE: expired {r.modified_count} active")}
    else:
        side = "long" if action == "BUY" else "short"
        symbol = p.get("db_symbol", "MNQ")
        minutes = 3 if legacy else int(p.get("cooldown_min", 3))
        existing = await db.signals.find_one({"ingest_key": key})
        if existing is None and await _is_cooldown_dup(db, symbol, side, minutes):
            reason = "Signal already active" if legacy else f"Same-side signal within {minutes}m cooldown"
            res = {"result": "duplicate", "notify": False, "signal_id": None,
                   "body": {"status": "duplicate", "reason": reason},
                   "event": (False, f"duplicate: {action} @ {p['price']}")}
        else:
            if existing is None:
                await db.signals.update_one({"ingest_key": key}, {"$setOnInsert": _signal_doc(p, side, key)},
                                            upsert=True)
                existing = await db.signals.find_one({"ingest_key": key})
            res = {"result": "created", "notify": True, "signal_id": existing["id"],
                   "body": _body_for(p, existing), "event": (True, f"created: {action} @ {p['price']}")}
    res["event"] = list(res["event"])
    await db.signal_ingest_audit.update_one({"workflow_id": key}, {"$setOnInsert": {"persist_result": res}},
                                            upsert=True)
    stored = await db.signal_ingest_audit.find_one({"workflow_id": key})
    return stored["persist_result"]


async def _default_discord_sender(doc: dict) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not url or url == "REPLACE_WITH_YOUR_DISCORD_WEBHOOK_URL":
        return False
    import httpx
    from server import _build_discord_payload  # same branded embed as the API (needs backend deps)
    async with httpx.AsyncClient() as c:
        resp = await c.post(url, json=_build_discord_payload(doc), timeout=5.0)
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"Discord HTTP {resp.status_code}")  # retried by Temporal
    return True


@activity.defn
async def notify_discord(signal_id: str) -> bool:
    """Sends at most once per signal: skips when discord_sent is already true."""
    db = _get_db()
    doc = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not doc:
        return False
    if doc.get("discord_sent"):
        return True
    sender = _discord_sender or _default_discord_sender
    sent = await sender(doc)
    if sent:
        await db.signals.update_one({"id": signal_id}, {"$set": {"discord_sent": True}})
    return bool(sent)


@activity.defn
async def write_audit(rec: Dict[str, Any]) -> None:
    """Final audit record (no secret is ever passed here) + the signal_events line the UI reads."""
    db = _get_db()
    await ensure_indexes(db)
    rec = {k: v for k, v in rec.items() if k != "secret"}
    now = datetime.now(timezone.utc)
    try:
        recv = datetime.fromisoformat(rec.get("received_at_api_utc") or now.isoformat())
    except ValueError:
        recv = now
    prior = await db.signal_ingest_audit.find_one({"workflow_id": rec["workflow_id"], "finalized": True})
    await db.signal_ingest_audit.update_one(
        {"workflow_id": rec["workflow_id"]},
        {"$set": {**rec, "finalized": True, "received_at_et": recv.astimezone(ET).isoformat(),
                  "finalized_at_utc": now.isoformat()}},
        upsert=True)
    if prior is None:
        ok, status, detail = rec.get("event_ok", False), rec.get("http_status", 200), rec.get("event_detail", "")
        await db.signal_events.insert_one({"ts": now.isoformat(), "ok": ok, "status": status,
                                           "detail": str(detail)[:300], "action": rec.get("action", ""),
                                           "source": rec.get("source", "")})
