"""Signal Pipeline — the missing middle layer (Phase 2, Tasks 3+4+5).

Sequence (order §7): ingest event → schema/data validation → timestamp and
session normalization (ET) → freshness check → closed-candle gate →
strategy evaluation → deterministic classification → risk-policy validation
→ persistence → journal. The store write IS the journal for signal records;
there is no second journal and no parallel database (order §7).

Persistence choice — SQLite, one local file (default
``backend/data/signal_records.db``, override ``SIGNAL_RECORDS_DB``):
the pipeline needs indexed idempotency lookups and atomic
insert-if-absent semantics, which JSONL cannot provide without a full scan
and a race window; SQLite is serverless, transactional, already the
ecosystem's local-store pattern, and — critically — it is a LOCAL file.
This module never touches the production Mongo, never imports
``server.py``, and never calls Stage 2's order path.

Hard rules enforced here (order §7):

- Missing or stale data never produces a valid signal: stale input becomes
  a persisted NO_TRADE rejection carrying the stale-data reason.
- An open candle never counts as a closed confirmation: it becomes a
  persisted NO_TRADE rejection.
- Duplicate events create nothing: the idempotency key is checked before
  evaluation and enforced by a UNIQUE constraint at insert.
- Out-of-order events are never journaled as fresh (battery finding
  F-1): an event whose signal candle is older than the journaled
  watermark for its (strategy, instrument, timeframe) — the timeframe
  joined the key in correction round 2, per Zelator's specification —
  is preserved as a NO_TRADE / OUT_OF_ORDER rejection in the store's
  audit table and returned as REJECTED. The watermark is a MAX over
  the journal, so it survives restart and never moves backward; equal
  timestamps stay with idempotency.
- Malformed numbers persist nothing (battery finding F-2): Strategy B
  bars are numeric-validated at ingestion, and the contract validator
  numeric-checks every record's market state and risk fields before
  persistence — a negative or spelled-out price is a validation error,
  never a qualified signal.
- Malformed identifiers and price-less alerts persist nothing
  (correction round 2, finding F-4): a present instrument identifier
  must be exactly "MNQ" (an absent one defaults), and a Strategy A
  alert must carry a real, finite, positive price — the same
  ingestion standard Strategy B bar data is held to.
- A strategy rejection stays a rejection; no AI text exists in this layer
  that could override a deterministic gate (the explanation block is built
  deterministically FROM the verdict, after it).
- Persistence failure fails closed: the record is marked
  PERSISTENCE_FAILED and :class:`PipelinePersistenceError` is raised —
  never silently dropped, never reported as journaled.
- **Paper-order firewall:** while ``risk_approval_status != APPROVED``
  (the standing state — no approved dollar-risk rule exists), this pipeline
  creates signal records ONLY. It contains no reference to any order, fill,
  or position constructor. Signal != fill != position != outcome.

Strategy separation (order §8): Strategy B is evaluated by the EXISTING
``bot_b.evaluate_bot_b`` detector, unmodified. Strategy A is NOT
re-implemented — its authoritative detector is the TradingView/Pine alert;
the adapter records the gate results the alert supplies and stamps every
gate it cannot verify ``NOT_EVALUABLE``. Records are never relabeled
between strategies (the contract's anti-relabel validation enforces this).
"""
from __future__ import annotations

import json
import math
import os
import sqlite3
from datetime import datetime, time, timezone
from typing import Any, Callable, Dict, Optional
from zoneinfo import ZoneInfo

import bot_b
import signal_contract as sc

ET = ZoneInfo("America/New_York")

DEFAULT_MAX_DATA_AGE_SECONDS = 300

#: Strategy A gate keys, in Six Gates order (University lesson l7).
STRATEGY_A_GATES = ("G1", "G2", "G3", "G4", "G5", "G6")


class PipelinePersistenceError(RuntimeError):
    """Fail-closed persistence failure. Carries the un-persisted record."""

    def __init__(self, message: str, record: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.record = record


class PersistenceError(RuntimeError):
    """Raised by a store when a write cannot be completed."""


# --------------------------------------------------------------------------
# Store
# --------------------------------------------------------------------------

def default_store_path() -> str:
    env = os.environ.get("SIGNAL_RECORDS_DB")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "signal_records.db")


class SignalStore:
    """Local SQLite store for contract signal records (the signal journal)."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or default_store_path()
        parent = os.path.dirname(os.path.abspath(self.path))
        os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS signal_records (
                idempotency_key TEXT PRIMARY KEY,
                signal_id TEXT UNIQUE NOT NULL,
                strategy_id TEXT NOT NULL,
                classification TEXT NOT NULL,
                record_json TEXT NOT NULL,
                persisted_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_by_idempotency_key(self, key: str) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT record_json FROM signal_records WHERE idempotency_key = ?", (key,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, rec: Dict[str, Any]) -> None:
        """Insert a validated record. Raises PersistenceError on any failure."""
        sc.validate_signal_record(rec)
        try:
            self._conn.execute(
                "INSERT INTO signal_records (idempotency_key, signal_id, strategy_id,"
                " classification, record_json, persisted_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    rec["idempotency_key"],
                    rec["signal_id"],
                    rec["strategy_id"],
                    rec["classification"]["classification"],
                    sc.to_json(rec),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"signal store write failed: {exc}") from exc

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM signal_records").fetchone()[0])

    # -- ordering watermark + out-of-order audit (battery finding F-1) ---

    def watermark(
        self, strategy_id: str, instrument: str, timeframe: Optional[str] = None
    ) -> Optional[str]:
        """Newest signal-candle timestamp journaled for (strategy,
        instrument, timeframe), as an ISO string, or None if nothing is
        journaled for that key.

        The key includes the timeframe (Zelator's correction-round
        specification): ordering is enforced independently per
        timeframe, so a newer 5m record never blocks a 1m event and a
        newer 1m record never blocks a 5m event. ``timeframe=None``
        keeps the legacy unfiltered scan for direct callers only; the
        pipeline always passes the event's timeframe.

        Derived by a MAX scan over the journaled records themselves, so
        it survives restart with no separate state to corrupt, and it
        never moves backward: it is by construction the maximum of what
        the journal already holds. Audit (out-of-order) records do NOT
        feed the watermark — they are precisely the events that arrived
        behind it.
        """
        best: Optional[datetime] = None
        rows = self._conn.execute(
            "SELECT record_json FROM signal_records WHERE strategy_id = ?",
            (strategy_id,),
        ).fetchall()
        for (payload,) in rows:
            try:
                rec = json.loads(payload)
            except ValueError:
                continue
            if rec.get("instrument") != instrument:
                continue
            if timeframe is not None and rec.get("timeframe") != timeframe:
                continue
            ts = (rec.get("market_state") or {}).get("candle_timestamp") or rec.get(
                "data_timestamp"
            )
            if not ts:
                continue
            try:
                dt = _parse_ts(ts)
            except (ValueError, TypeError):
                continue
            if best is None or dt > best:
                best = dt
        return _iso(best) if best is not None else None

    #: Audit table for out-of-order rejections. Created LAZILY, on the
    #: first rejected out-of-order event — never at store init — so a
    #: journal that has seen no out-of-order event keeps exactly its one
    #: table (battery scenario 20), and no order-shaped table ever exists.
    _AUDIT_TABLE = "signal_rejection_audit"

    def _ensure_audit_table(self) -> None:
        self._conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self._AUDIT_TABLE} (
                idempotency_key TEXT PRIMARY KEY,
                signal_id TEXT UNIQUE NOT NULL,
                strategy_id TEXT NOT NULL,
                rejection_status TEXT NOT NULL,
                record_json TEXT NOT NULL,
                persisted_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def _audit_table_exists(self) -> bool:
        row = self._conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name = ?",
            (self._AUDIT_TABLE,),
        ).fetchone()
        return bool(row and row[0])

    def put_rejection(self, rec: Dict[str, Any]) -> None:
        """Persist a NO_TRADE rejection record to the audit table.

        Used for out-of-order events (finding F-1): the record is
        preserved for audit but is NOT a journal entry — it does not
        enter ``signal_records``, does not affect ``count()``, and does
        not move the watermark. Raises PersistenceError on failure so
        the pipeline can fail closed exactly as for journal writes.
        """
        sc.validate_signal_record(rec)
        try:
            self._ensure_audit_table()
            self._conn.execute(
                f"INSERT INTO {self._AUDIT_TABLE} (idempotency_key, signal_id,"
                " strategy_id, rejection_status, record_json, persisted_at)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                (
                    rec["idempotency_key"],
                    rec["signal_id"],
                    rec["strategy_id"],
                    (rec.get("classification") or {}).get("rejection_status"),
                    sc.to_json(rec),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            self._conn.commit()
        except sqlite3.Error as exc:
            raise PersistenceError(f"signal audit write failed: {exc}") from exc

    def latest_qualified(
        self, strategy_id: str, instrument: str, timeframe: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """The qualified (LONG/SHORT) journaled record with the newest
        signal-candle timestamp for (strategy, instrument[, timeframe]),
        or None. This is the consumer "latest" read finding F-1 was
        about: because out-of-order events never enter the journal, this
        read can never regress to an older observation."""
        best: Optional[Dict[str, Any]] = None
        best_dt: Optional[datetime] = None
        rows = self._conn.execute(
            "SELECT record_json FROM signal_records WHERE strategy_id = ?",
            (strategy_id,),
        ).fetchall()
        for (payload,) in rows:
            try:
                rec = json.loads(payload)
            except ValueError:
                continue
            if rec.get("instrument") != instrument:
                continue
            if timeframe is not None and rec.get("timeframe") != timeframe:
                continue
            if (rec.get("classification") or {}).get("classification") not in (
                "LONG",
                "SHORT",
            ):
                continue
            ts = (rec.get("market_state") or {}).get("candle_timestamp") or rec.get(
                "data_timestamp"
            )
            if not ts:
                continue
            try:
                dt = _parse_ts(ts)
            except (ValueError, TypeError):
                continue
            if best_dt is None or dt > best_dt:
                best, best_dt = rec, dt
        return best

    def get_rejections(self) -> list:
        """All audit (out-of-order) rejection records, oldest first."""
        if not self._audit_table_exists():
            return []
        rows = self._conn.execute(
            f"SELECT record_json FROM {self._AUDIT_TABLE} ORDER BY persisted_at"
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def rejection_count(self) -> int:
        if not self._audit_table_exists():
            return 0
        return int(
            self._conn.execute(f"SELECT COUNT(*) FROM {self._AUDIT_TABLE}").fetchone()[0]
        )

    def close(self) -> None:
        self._conn.close()


# --------------------------------------------------------------------------
# Time / session helpers
# --------------------------------------------------------------------------

def _parse_ts(value: Any) -> datetime:
    """Accept epoch seconds or an ISO-8601 string; return aware UTC datetime."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ET)  # naive input is read as ET, the market clock
        return dt.astimezone(timezone.utc)
    raise sc.SignalValidationError(f"unparseable timestamp: {value!r}")


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _session_for(dt_utc: datetime) -> str:
    """Session stamp (mapping GAP #9): RTH 09:30–16:00 ET Mon–Fri, else ETH."""
    et = dt_utc.astimezone(ET)
    if et.weekday() < 5 and time(9, 30) <= et.time() < time(16, 0):
        return "RTH"
    return "ETH"


# --------------------------------------------------------------------------
# Deterministic explanation (order §9 fallback label; built AFTER verdict)
# --------------------------------------------------------------------------

def _deterministic_explanation(
    rec: Dict[str, Any], *, data_limitations: list
) -> Dict[str, Any]:
    cls = rec["classification"]
    verdict = cls["classification"]
    if verdict in ("LONG", "SHORT") and cls["qualification_status"].startswith("qualified"):
        disposition = "EXPLAINED — deterministic evaluation qualified this signal"
        reasons = cls["qualification_reasons"]
    else:
        disposition = "EXPLAINED — deterministic evaluation did not qualify a trade"
        reasons = cls["rejection_reasons"] or cls["qualification_reasons"]
    return {
        "analyst_disposition": disposition,
        "explanation": (
            f"{rec['strategy_id']} evaluation at {rec['market_state'].get('price')}: "
            f"{verdict} ({cls['qualification_status']}). " + " ".join(reasons)
        ).strip(),
        "supporting_evidence_refs": [
            "classification.gate_results",
            "classification.qualification_reasons",
            "classification.rejection_reasons",
            "market_state",
        ],
        "contradictory_evidence": [],
        "data_limitations": data_limitations,
        "provider_metadata": {"provider": None, "model": None, "connected": False},
        "explanation_source": sc.EXPLANATION_SOURCE_FALLBACK,
        "review_status": "UNREVIEWED",
    }


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

class SignalPipeline:
    def __init__(
        self,
        store: SignalStore,
        *,
        max_data_age_seconds: float = DEFAULT_MAX_DATA_AGE_SECONDS,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        self.store = store
        self.max_data_age_seconds = max_data_age_seconds
        self._now_fn = now_fn or (lambda: datetime.now(timezone.utc))

    # -- public entry point ------------------------------------------------

    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Run one event through the pipeline.

        Returns an envelope: {status, created, order_created: False, record}.
        Raises SignalValidationError for malformed events and
        PipelinePersistenceError (fail-closed) when the journal write fails.
        """
        ctx = self._validate_and_normalize(event)

        # Idempotency (before evaluation): a duplicate creates nothing.
        existing = self.store.get_by_idempotency_key(ctx["idempotency_key"])
        if existing is not None:
            return {"status": "DUPLICATE", "created": False, "order_created": False, "record": existing}

        # Ordering guard (battery finding F-1; key refined to include
        # the timeframe in correction round 2, per Zelator's spec): an
        # event whose signal candle is OLDER than the journaled
        # watermark for its (strategy, instrument, timeframe) is out of
        # order. It is never journaled
        # as a fresh record — a consumer reading "latest" must never be
        # handed a stale-timeline record as current. The event is
        # preserved as a NO_TRADE / OUT_OF_ORDER rejection in the
        # store's audit table (audit trail kept, journal untouched, the
        # watermark — a MAX over the journal — cannot move backward).
        # Equal timestamps are NOT out of order: they remain governed
        # by idempotency above. Stores without a watermark method
        # (e.g. an injected test double) cannot be order-checked and
        # skip this guard.
        watermark_fn = getattr(self.store, "watermark", None)
        if callable(watermark_fn):
            watermark = watermark_fn(
                ctx["strategy_id"], ctx["instrument"], ctx["timeframe"]
            )
            if watermark is not None and ctx["data_dt"] < _parse_ts(watermark):
                rec = self._rejection_record(
                    ctx,
                    gate="EVENT_ORDERING",
                    rejection_status="OUT_OF_ORDER",
                    reason=(
                        f"event candle {ctx['candle_timestamp']} is older than the "
                        f"journaled watermark {watermark} for "
                        f"{ctx['strategy_id']}/{ctx['instrument']}/{ctx['timeframe']}; "
                        "out-of-order events are preserved in the audit trail, "
                        "never journaled as fresh records"
                    ),
                    stale=False,
                )
                return self._persist_rejection(rec)

        # Freshness gate: stale data -> persisted NO_TRADE rejection.
        age = (ctx["received_dt"] - ctx["data_dt"]).total_seconds()
        if age > self.max_data_age_seconds:
            rec = self._rejection_record(
                ctx,
                gate="DATA_FRESHNESS",
                rejection_status="STALE_DATA",
                reason=(
                    f"data is {age:.0f}s old at receipt; limit is "
                    f"{self.max_data_age_seconds:.0f}s — stale data never produces a valid signal"
                ),
                stale=True,
            )
            return self._persist(rec)

        # Closed-candle gate: an open candle is not a confirmation.
        if not ctx["candle_closed"]:
            rec = self._rejection_record(
                ctx,
                gate="CANDLE_CLOSED",
                rejection_status="OPEN_CANDLE",
                reason="the evaluated candle is still open; an open candle is never treated as a closed confirmation",
                stale=False,
            )
            return self._persist(rec)

        # Strategy evaluation (adapters are strictly separate).
        if ctx["strategy_id"] == sc.STRATEGY_B:
            rec = self._adapt_strategy_b(event, ctx)
        else:
            rec = self._adapt_strategy_a(event, ctx)

        # Risk-policy validation: the contract validator is the firewall —
        # it rejects any record carrying order fields while UNAPPROVED.
        sc.validate_signal_record(rec, expected_strategy_id=ctx["strategy_id"])
        return self._persist(rec)

    # -- step 1–3: validation + normalization -------------------------------

    def _validate_and_normalize(self, event: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(event, dict):
            raise sc.SignalValidationError("event is not an object")
        kind = event.get("event_kind")
        if kind not in ("strategy_b", "strategy_a"):
            raise sc.SignalValidationError(f"event_kind must be 'strategy_b' or 'strategy_a', got {kind!r}")
        for field in ("contract", "data_provider", "data_source"):
            value = event.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                raise sc.SignalValidationError(f"event is missing required field: {field}")

        # Instrument discipline (correction round 2, finding F-4): this
        # system trades MNQ only. An ABSENT instrument defaults to MNQ;
        # a PRESENT instrument must be exactly "MNQ". Before this check,
        # a foreign symbol ("ES") was journaled as a qualified record
        # under that instrument, and "" / None were silently repaired
        # to "MNQ" — malformed identifiers are now rejected at
        # ingestion and persist nothing.
        instrument = event.get("instrument", "MNQ")
        if instrument != "MNQ":
            raise sc.SignalValidationError(
                f"instrument must be 'MNQ' for strategy events in this system, "
                f"got {instrument!r}; invalid instrument identifiers are "
                "rejected at ingestion and persist nothing"
            )

        strategy_id = sc.STRATEGY_B if kind == "strategy_b" else sc.STRATEGY_A
        received_dt = _parse_ts(event["received_at"]) if event.get("received_at") else self._now_fn()

        if kind == "strategy_b":
            bars = event.get("bars_1m") or []
            # Ingestion data validation (battery finding F-2, sub-case
            # c): every bar's OHLC must be a real, finite, positive
            # number. Bot B sanitizes a malformed bar into a detector
            # rejection, which would journal the event as a NO_TRADE
            # record; malformed FEED data is a validation error instead
            # — it persists nothing. This validates the pipeline's
            # input, not the detector: bot_b is called unmodified with
            # whatever passes here.
            for idx, bar in enumerate(bars):
                if not isinstance(bar, dict):
                    raise sc.SignalValidationError(f"bars_1m[{idx}] is not an object")
                for field in ("open", "high", "low", "close"):
                    value = bar.get(field)
                    if (
                        isinstance(value, bool)
                        or not isinstance(value, (int, float))
                        or not math.isfinite(value)
                        or value <= 0
                    ):
                        raise sc.SignalValidationError(
                            f"bars_1m[{idx}].{field} must be a real, finite, "
                            f"positive number, got {value!r}; malformed bar "
                            "data is rejected at ingestion and persists nothing"
                        )
                volume = bar.get("volume")
                if volume is not None and (
                    isinstance(volume, bool)
                    or not isinstance(volume, (int, float))
                    or not math.isfinite(volume)
                    or volume < 0
                ):
                    raise sc.SignalValidationError(
                        f"bars_1m[{idx}].volume must be a real, finite, "
                        f"non-negative number, got {volume!r}"
                    )
            if bars:
                data_dt = _parse_ts(bars[-1]["time"])
                candle_ts = _iso(data_dt)
            elif event.get("data_timestamp"):
                data_dt = _parse_ts(event["data_timestamp"])
                candle_ts = _iso(data_dt)
            else:
                raise sc.SignalValidationError("strategy_b event carries no bars and no data_timestamp")
            candle_closed = bool(event.get("candle_closed", True))
            timeframe = "1m"  # the Strategy B record's stamped timeframe
        else:
            alert = event.get("alert") or {}
            if alert.get("bar_time") is None and event.get("data_timestamp") is None:
                raise sc.SignalValidationError("strategy_a event carries no alert bar_time or data_timestamp")
            # Strategy A price discipline (correction round 2, finding
            # F-4): the alert is a price-bearing event, held to the same
            # ingestion standard as Strategy B bar data. Before this
            # check, an alert with price=None was journaled as a
            # QUALIFIED record carrying no price at all; the contract
            # validator's numeric checks skip absent values, so presence
            # must be enforced here, at ingestion.
            alert_price = alert.get("price")
            if (
                isinstance(alert_price, bool)
                or not isinstance(alert_price, (int, float))
                or not math.isfinite(alert_price)
                or alert_price <= 0
            ):
                raise sc.SignalValidationError(
                    f"strategy_a alert price must be a real, finite, positive "
                    f"number, got {alert_price!r}; a price-less or malformed "
                    "alert is rejected at ingestion and persists nothing"
                )
            data_dt = _parse_ts(alert.get("bar_time", event.get("data_timestamp")))
            candle_ts = _iso(data_dt)
            candle_closed = bool(alert.get("candle_closed", event.get("candle_closed", True)))
            # Must match the timeframe the Strategy A adapter stamps on
            # the record, so the ordering watermark groups consistently.
            timeframe = alert.get("timeframe") or "1m"

        return {
            "strategy_id": strategy_id,
            "instrument": instrument,
            "timeframe": timeframe,
            "contract": event["contract"],
            "data_provider": event["data_provider"],
            "data_source": event["data_source"],
            "environment": event.get("environment") or "PAPER",
            "source_event_id": event.get("source_event_id"),
            "data_dt": data_dt,
            "received_dt": received_dt,
            "candle_timestamp": candle_ts,
            "candle_closed": candle_closed,
            "session": _session_for(data_dt),
            "idempotency_key": event.get("idempotency_key")
            or sc.derive_idempotency_key(strategy_id, candle_ts, event.get("source_event_id")),
        }

    def _base_kwargs(self, ctx: Dict[str, Any], *, strategy_version: str, timeframe: str) -> Dict[str, Any]:
        return dict(
            strategy_id=ctx["strategy_id"],
            strategy_version=strategy_version,
            instrument=ctx["instrument"],
            contract=ctx["contract"],
            data_provider=ctx["data_provider"],
            data_source=ctx["data_source"],
            data_timestamp=_iso(ctx["data_dt"]),
            received_timestamp=_iso(ctx["received_dt"]),
            session=ctx["session"],
            timeframe=timeframe,
            environment=ctx["environment"],
            source_event_id=ctx["source_event_id"],
            idempotency_key=ctx["idempotency_key"],
            candle_timestamp=ctx["candle_timestamp"],
        )

    def _rejection_record(self, ctx: Dict[str, Any], *, gate: str, rejection_status: str, reason: str, stale: bool) -> Dict[str, Any]:
        version = sc.STRATEGY_B_VERSION if ctx["strategy_id"] == sc.STRATEGY_B else sc.STRATEGY_A_VERSION
        rec = sc.new_signal_record(
            **self._base_kwargs(ctx, strategy_version=version, timeframe=ctx["timeframe"]),
            market_state={
                "price": None,
                "candle_timestamp": ctx["candle_timestamp"],
                "candle_closed": ctx["candle_closed"],
                "data_freshness": "STALE" if stale else "FRESH",
                "data_quality": "REJECTED_BY_PIPELINE_GATE",
            },
            classification={
                "classification": "NO_TRADE",
                "qualification_status": "rejected",
                "rejection_status": rejection_status,
                "gate_results": {gate: "FAIL"},
                "qualification_reasons": [],
                "rejection_reasons": [reason],
                "missing_data_reasons": [],
                "stale_data_reasons": [reason] if stale else [],
            },
        )
        rec["ai_explanation"] = _deterministic_explanation(
            rec,
            data_limitations=["Evaluation stopped at a pipeline gate; no strategy evaluation was performed."],
        )
        return sc.validate_signal_record(rec, expected_strategy_id=ctx["strategy_id"])

    def _persist(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self.store.put(rec)
        except PersistenceError as exc:
            rec["persistence_status"] = "PERSISTENCE_FAILED"
            raise PipelinePersistenceError(
                f"fail-closed: signal record was NOT journaled ({exc})", record=rec
            ) from exc
        rec["persistence_status"] = "PERSISTED"
        return {"status": "RECORDED", "created": True, "order_created": False, "record": rec}

    def _persist_rejection(self, rec: Dict[str, Any]) -> Dict[str, Any]:
        """Persist an out-of-order rejection to the store's audit table
        (finding F-1) and return the REJECTED envelope. Fail-closed,
        same contract as _persist: if the audit write cannot be made,
        the failure surfaces as PipelinePersistenceError rather than
        silently dropping the event."""
        put_rejection = getattr(self.store, "put_rejection", None)
        if not callable(put_rejection):
            rec["persistence_status"] = "PERSISTENCE_FAILED"
            raise PipelinePersistenceError(
                "fail-closed: store cannot preserve the out-of-order "
                "rejection in an audit trail; event NOT processed",
                record=rec,
            )
        try:
            put_rejection(rec)
        except PersistenceError as exc:
            rec["persistence_status"] = "PERSISTENCE_FAILED"
            raise PipelinePersistenceError(
                f"fail-closed: out-of-order rejection was NOT preserved ({exc})",
                record=rec,
            ) from exc
        rec["persistence_status"] = "PERSISTED"
        return {
            "status": "REJECTED",
            "created": False,
            "order_created": False,
            "audit_recorded": True,
            "record": rec,
        }

    # -- Strategy B adapter ---------------------------------------------------

    def _adapt_strategy_b(self, event: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Call the EXISTING Bot B detector unmodified; convert its output.

        Classification mapping per BOTB-SIGNAL-MAPPING.md §4 — three of the
        five Bot B states collapse to NO_TRADE but keep distinct
        qualification statuses.
        """
        det = bot_b.evaluate_bot_b(
            event.get("bars_1m"),
            range_high=event.get("range_high"),
            range_low=event.get("range_low"),
            risk_limit_dollars=event.get("risk_limit_dollars"),
            exit_conditions=event.get("exit_conditions"),
            approved=event.get("approved"),
            snapshot=event.get("snapshot"),
            now=ctx["received_dt"],
        )
        ev = det.get("evaluator") or {}
        rules = ev.get("rules") or {}
        gate_results = {k: ("PASS" if v else "FAIL") for k, v in sorted(rules.items())}

        state = det["classification"]
        direction = det.get("direction")
        if state == "VALIDATED PAPER SIGNAL" and direction in ("LONG", "SHORT"):
            classification, q_status, r_status = direction, "qualified", None
        elif state == "NO TRADE":
            classification, q_status, r_status = "NO_TRADE", "rejected", "STRATEGY_REJECTED"
        elif state == "WAITING":
            classification, q_status, r_status = "NO_TRADE", "awaiting_data_or_range", None
        elif state == "POTENTIAL SETUP":
            classification, q_status, r_status = "NO_TRADE", "watch", None
        elif state == "CONFIRMATION PENDING":
            classification, q_status, r_status = "NO_TRADE", "pending_parameters_or_confirmation", None
        else:  # pragma: no cover - detector contract guarantees the five states
            classification, q_status, r_status = "NO_TRADE", "not_evaluated", None

        rejection_reasons = list(det.get("conditions_failed") or [])
        if classification == "NO_TRADE" and det.get("explanation"):
            rejection_reasons.append(det["explanation"])
        missing_reasons = [
            f"data rejected: {f}" for f in rejection_reasons if f.startswith("data rejected:")
        ]

        ema9 = (det.get("ema") or {}).get("ema9_5m")
        ema21 = (det.get("ema") or {}).get("ema21_5m")
        ema_rel = None
        if ema9 is not None and ema21 is not None:
            ema_rel = "EMA9 above EMA21" if ema9 > ema21 else ("EMA9 below EMA21" if ema9 < ema21 else "EMA9 equal to EMA21")

        rng = det.get("range") or {}
        trade = det.get("paper_trade") or {}
        entry_ref = trade.get("entry_price")
        stop_level = trade.get("invalidation")
        stop_distance = (
            abs(entry_ref - stop_level)
            if isinstance(entry_ref, (int, float)) and isinstance(stop_level, (int, float))
            else None
        )

        rec = sc.new_signal_record(
            **self._base_kwargs(ctx, strategy_version=sc.STRATEGY_B_VERSION, timeframe="1m"),
            market_state={
                "price": det.get("price"),
                "context_15m": (ev.get("timeframes") or {}).get("15m_context"),
                "bias_5m": det.get("confirmation_5m"),
                "trigger_1m": det.get("entry_1m"),
                "vwap": {"value": (det.get("vwap") or {}).get("value_5m"),
                         "relationship": (det.get("vwap") or {}).get("position")},
                "ema9": ema9,
                "ema21": ema21,
                "ema_relationship": ema_rel,
                "rsi14": det.get("rsi14_5m"),
                "range_high": rng.get("high"),
                "range_low": rng.get("low"),
                # For Strategy B the supplied range boundaries ARE the
                # operative S/R levels (mapping row 27).
                "confirmed_sr_level": (rng.get("low") if direction == "LONG" else rng.get("high"))
                if classification in ("LONG", "SHORT") else None,
                "candle_timestamp": ctx["candle_timestamp"],
                "candle_closed": ctx["candle_closed"],
                "data_freshness": "FRESH",
                "data_quality": "EVALUATED",
                "data_label": det.get("data_label"),
            },
            classification={
                "classification": classification,
                "qualification_status": q_status,
                "rejection_status": r_status,
                "gate_results": gate_results,
                "qualification_reasons": list(det.get("conditions_passed") or [])
                + ([det["explanation"]] if classification in ("LONG", "SHORT") and det.get("explanation") else []),
                "rejection_reasons": rejection_reasons if classification == "NO_TRADE" else [],
                "missing_data_reasons": missing_reasons,
                "stale_data_reasons": [],
            },
            risk={
                # Analytical fields only. proposed_entry is the signal-time
                # REFERENCE price (mapping C2) — never a fill. Bot B computes
                # no target (mapping row 40) and no quantity exists.
                "proposed_entry": entry_ref,
                "structural_stop": stop_level,
                "target": None,
                "stop_distance_points": stop_distance,
                "reward_risk": None,
                "quantity": None,
                "max_simulated_exposure": None,
                "risk_config_version": sc.RISK_CONFIG_VERSION_UNAPPROVED,
                "risk_approval_status": sc.RISK_UNAPPROVED,
                "exit_conditions": trade.get("exit_conditions") or event.get("exit_conditions"),
            },
        )
        rec["ai_explanation"] = _deterministic_explanation(
            rec,
            data_limitations=[
                "Detector evaluated the bars supplied in the event; the pipeline does not independently verify the feed.",
                "A qualified Strategy B record is an analytical observation: risk approval is UNAPPROVED, so no paper order may be created from it.",
            ],
        )
        return sc.validate_signal_record(rec, expected_strategy_id=sc.STRATEGY_B)

    # -- Strategy A adapter ---------------------------------------------------

    def _adapt_strategy_a(self, event: Dict[str, Any], ctx: Dict[str, Any]) -> Dict[str, Any]:
        """Record a TradingView/Pine Strategy A alert. NO gate re-implementation.

        The alert is authoritative for detection. Gates the payload supplies
        are recorded as reported; every gate it does not supply is stamped
        NOT_EVALUABLE — never a fabricated pass. A record can qualify only
        when the alert reports all six gates PASS with a direction; even
        then its status is 'qualified_alert_reported' (reported, not
        pipeline-verified).
        """
        alert = event.get("alert") or {}
        supplied_raw = alert.get("gate_results") or {}
        gate_results: Dict[str, str] = {}
        for gate in STRATEGY_A_GATES:
            value = supplied_raw.get(gate)
            gate_results[gate] = value if value in ("PASS", "FAIL") else "NOT_EVALUABLE"

        direction = alert.get("direction") if alert.get("direction") in ("LONG", "SHORT") else None
        unevaluable = [g for g, v in gate_results.items() if v == "NOT_EVALUABLE"]
        failed = [g for g, v in gate_results.items() if v == "FAIL"]

        if direction and not failed and not unevaluable:
            classification = direction
            q_status, r_status = "qualified_alert_reported", None
            q_reasons = ["All six gates reported PASS by the authoritative TradingView alert; not independently verified by this pipeline."]
            r_reasons: list = []
        else:
            classification, q_status = "NO_TRADE", "rejected"
            r_status = "GATE_NOT_EVALUABLE" if unevaluable else "GATE_FAILED"
            q_reasons = []
            r_reasons = []
            if failed:
                r_reasons.append(f"Alert reported gate failure: {', '.join(failed)}.")
            if unevaluable:
                r_reasons.append(
                    f"Gates not evaluable from the alert payload: {', '.join(unevaluable)} — "
                    "unverifiable gates are never treated as passes."
                )
            if not direction:
                r_reasons.append("Alert carried no LONG/SHORT direction.")

        price = alert.get("price")
        stop_level = alert.get("structural_stop")
        stop_distance = (
            abs(price - stop_level)
            if isinstance(price, (int, float)) and isinstance(stop_level, (int, float))
            else None
        )
        ema9, ema21 = alert.get("ema9"), alert.get("ema21")
        ema_rel = None
        if isinstance(ema9, (int, float)) and isinstance(ema21, (int, float)):
            ema_rel = "EMA9 above EMA21" if ema9 > ema21 else ("EMA9 below EMA21" if ema9 < ema21 else "EMA9 equal to EMA21")
        vwap_value = alert.get("vwap")
        vwap_rel = None
        if isinstance(price, (int, float)) and isinstance(vwap_value, (int, float)):
            vwap_rel = "price above VWAP" if price >= vwap_value else "price below VWAP"

        rec = sc.new_signal_record(
            **self._base_kwargs(ctx, strategy_version=sc.STRATEGY_A_VERSION, timeframe=alert.get("timeframe") or "1m"),
            market_state={
                "price": price,
                "context_15m": alert.get("context_15m"),
                "bias_5m": alert.get("bias_5m"),
                "trigger_1m": alert.get("trigger_1m"),
                "vwap": {"value": vwap_value, "relationship": vwap_rel},
                "ema9": ema9,
                "ema21": ema21,
                "ema_relationship": ema_rel,
                "rsi14": alert.get("rsi14"),
                "range_high": alert.get("range_high"),
                "range_low": alert.get("range_low"),
                "confirmed_sr_level": alert.get("level"),
                "candle_timestamp": ctx["candle_timestamp"],
                "candle_closed": ctx["candle_closed"],
                "data_freshness": "FRESH",
                "data_quality": "ALERT_REPORTED",
                "gate_source": "tradingview_alert_payload",
            },
            classification={
                "classification": classification,
                "qualification_status": q_status,
                "rejection_status": r_status,
                "gate_results": gate_results,
                "qualification_reasons": q_reasons,
                "rejection_reasons": r_reasons,
                "missing_data_reasons": [],
                "stale_data_reasons": [],
            },
            risk={
                "proposed_entry": price,
                "structural_stop": stop_level,
                "target": None,
                "stop_distance_points": stop_distance,
                "reward_risk": None,
                "quantity": None,
                "max_simulated_exposure": None,
                "risk_config_version": sc.RISK_CONFIG_VERSION_UNAPPROVED,
                "risk_approval_status": sc.RISK_UNAPPROVED,
                "exit_conditions": alert.get("exit_conditions"),
            },
        )
        rec["ai_explanation"] = _deterministic_explanation(
            rec,
            data_limitations=[
                "Gate results are as reported by the TradingView alert payload; the pipeline cannot independently verify Pine-side gate evaluation.",
                "Risk approval is UNAPPROVED: this record is an observation, never an order.",
            ],
        )
        return sc.validate_signal_record(rec, expected_strategy_id=sc.STRATEGY_A)
