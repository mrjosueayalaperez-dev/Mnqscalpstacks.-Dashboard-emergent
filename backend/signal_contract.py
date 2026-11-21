"""Unified Structured Signal Contract — schema version 1.0 (Phase 2, Tasks 3+5).

One versioned record for every strategy evaluation in the MNQ Command
Dashboard, per the Phase 2 execution order §6 and the field-level mapping in
``BOTB-SIGNAL-MAPPING.md`` (50 mapped rows, 6 strict gaps filled here from
pipeline context: schema_version, contract, data_provider, session,
strategy_version, risk-config version).

Design rules (hard, enforced by :func:`validate_signal_record`):

- A record is an **analytical observation**, never an executable order.
  Signal != fill != position != outcome (mapping disagreement D1).
- **No approved dollar-risk rule exists.** ``risk_approval_status`` defaults
  to ``"UNAPPROVED"`` and, while it is not ``"APPROVED"``, ``quantity`` and
  ``max_simulated_exposure`` must be ``None`` and no target may be populated
  — a validator rejects any record that smuggles in invented risk.
- Provenance is mandatory: a record that cannot say which instrument,
  contract, provider, and strategy version produced it is rejected.
- Numeric sanity is mandatory (battery finding F-2): every present
  price/entry/stop/target/VWAP/EMA value must be a real, finite number
  (never a bool, never a string) and prices must be > 0; RSI and other
  non-price numerics must be real and finite. Malformed numbers are
  rejected at validation — they never persist as signals.
- A record's ``strategy_id`` is stamped at construction and is part of its
  ``idempotency_key``; a relabeled copy cannot validate against the original
  strategy and cannot overwrite the original in the store.
- Clocks: timestamps are stored as UTC ISO-8601, with the America/New_York
  rendering carried alongside (mapping conflict C7).

This module is pure: no I/O, no network, no imports from ``server.py`` or
any ``connect_core`` file.
"""
from __future__ import annotations

import hashlib
import json
import math
import uuid
from typing import Any, Dict, Optional

SCHEMA_VERSION = "1.0"

STRATEGY_A = "STRATEGY_A"
STRATEGY_B = "STRATEGY_B"
STRATEGY_IDS = (STRATEGY_A, STRATEGY_B)

#: Bot B's governing document, cited in bot_b.py / BOT_B_DETECTOR_SPEC.md.
STRATEGY_B_VERSION = "MQU-SB-001 v1.0"
#: Strategy A's authoritative implementation is the TradingView/Pine alert;
#: the source does not stamp a version, and this contract does not invent one.
STRATEGY_A_VERSION = "Six Gates — TradingView/Pine (authoritative; version not stamped by source)"

CLASSIFICATIONS = ("LONG", "SHORT", "NO_TRADE")
ENVIRONMENTS = ("SIM", "PAPER", "TEST")

RISK_APPROVED = "APPROVED"
RISK_UNAPPROVED = "UNAPPROVED"
#: The risk-config version stamped while no founder-approved risk rule exists.
RISK_CONFIG_VERSION_UNAPPROVED = "UNAPPROVED-v0"

#: Explanation-source label used while no provider is connected (order §9).
EXPLANATION_SOURCE_FALLBACK = "DETERMINISTIC_FALLBACK — PROVIDER_NOT_CONNECTED"
EXPLANATION_SOURCE_LIVE = "LIVE_PROVIDER"

#: Provenance fields that must be present and non-empty on every record.
#: ``source_event_id`` is deliberately NOT in this list: Bot B evaluations
#: have no upstream event ID (mapping row 14), so it may be None — identity
#: is then carried by the derived ``idempotency_key``.
REQUIRED_PROVENANCE = (
    "signal_id",
    "schema_version",
    "instrument",
    "contract",
    "data_provider",
    "data_source",
    "data_timestamp",
    "received_timestamp",
    "session",
    "timeframe",
    "strategy_id",
    "strategy_version",
    "environment",
    "idempotency_key",
)

#: Order-shaped fields that must stay empty while risk is UNAPPROVED.
_ORDER_FIELDS_WHEN_UNAPPROVED = ("quantity", "max_simulated_exposure", "target")


class SignalValidationError(ValueError):
    """Raised when a signal record violates the contract."""


def _check_numeric(field: str, value: Any, *, price: bool = False) -> None:
    """Numeric sanity for one market-state / risk field (finding F-2).

    A present value must be a real number — ``int``/``float``, never
    ``bool`` (a bool is an int subclass and must not smuggle through),
    never a string (a spelled-out price like "twenty-six thousand" is
    not a price) — and finite. Prices must additionally be > 0: a
    negative or zero price is malformed market data, not a signal.
    ``None`` means the field is absent and is not checked here.
    """
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SignalValidationError(
            f"{field} must be a real number, got {value!r} "
            f"({type(value).__name__}); non-numeric market data is rejected"
        )
    if not math.isfinite(value):
        raise SignalValidationError(f"{field} must be finite, got {value!r}")
    if price and value <= 0:
        raise SignalValidationError(
            f"{field} must be > 0 (it is a price), got {value!r}; "
            "a non-positive price is malformed market data, not a signal"
        )


def derive_idempotency_key(
    strategy_id: str,
    candle_timestamp: Optional[str],
    source_event_id: Optional[str] = None,
) -> str:
    """Deterministic idempotency key (mapping row 15 / disagreement D4).

    The strategy is embedded in the key so the same event evaluated by two
    strategies yields two records, and a relabeled copy produces a different
    key — it can never overwrite the original strategy's record.
    """
    basis = f"{strategy_id}|{source_event_id or ''}|{candle_timestamp or ''}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return f"{strategy_id}:{digest}"


def new_signal_record(
    *,
    strategy_id: str,
    strategy_version: str,
    instrument: str,
    contract: str,
    data_provider: str,
    data_source: str,
    data_timestamp: str,
    received_timestamp: str,
    session: str,
    timeframe: str,
    environment: str = "PAPER",
    source_event_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    candle_timestamp: Optional[str] = None,
    market_state: Optional[Dict[str, Any]] = None,
    classification: Optional[Dict[str, Any]] = None,
    risk: Optional[Dict[str, Any]] = None,
    ai_explanation: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a contract record with safe defaults, then validate it.

    Risk defaults are the standing rule: UNAPPROVED, quantity None, no
    target, no exposure. Callers may add *analytical* risk fields (proposed
    entry reference, structural stop, derived stop distance) but never
    order fields while unapproved — validation enforces this.
    """
    rec: Dict[str, Any] = {
        "signal_id": uuid.uuid4().hex,
        "schema_version": SCHEMA_VERSION,
        "instrument": instrument,
        "contract": contract,
        "data_provider": data_provider,
        "data_source": data_source,
        "data_timestamp": data_timestamp,
        "received_timestamp": received_timestamp,
        "session": session,
        "timeframe": timeframe,
        "strategy_id": strategy_id,
        "strategy_version": strategy_version,
        "environment": environment,
        "source_event_id": source_event_id,
        "idempotency_key": idempotency_key
        or derive_idempotency_key(strategy_id, candle_timestamp, source_event_id),
        "market_state": market_state or {},
        "classification": classification
        or {
            "classification": "NO_TRADE",
            "qualification_status": "not_evaluated",
            "rejection_status": None,
            "gate_results": {},
            "qualification_reasons": [],
            "rejection_reasons": [],
            "missing_data_reasons": [],
            "stale_data_reasons": [],
        },
        "risk": risk
        or {
            "proposed_entry": None,
            "structural_stop": None,
            "target": None,
            "stop_distance_points": None,
            "reward_risk": None,
            "quantity": None,
            "max_simulated_exposure": None,
            "risk_config_version": RISK_CONFIG_VERSION_UNAPPROVED,
            "risk_approval_status": RISK_UNAPPROVED,
            "exit_conditions": None,
        },
        "ai_explanation": ai_explanation
        or {
            "analyst_disposition": None,
            "explanation": None,
            "supporting_evidence_refs": [],
            "contradictory_evidence": [],
            "data_limitations": [],
            "provider_metadata": {"provider": None, "model": None, "connected": False},
            "explanation_source": EXPLANATION_SOURCE_FALLBACK,
            "review_status": "UNREVIEWED",
        },
        "persistence_status": "NOT_PERSISTED",
    }
    return validate_signal_record(rec)


def validate_signal_record(
    rec: Dict[str, Any], *, expected_strategy_id: Optional[str] = None
) -> Dict[str, Any]:
    """Validate a contract record; raise SignalValidationError on violation.

    Returns the record unchanged on success so callers can chain.
    ``expected_strategy_id`` is the anti-relabel guard: adapters and the
    store validate against the strategy they are processing, so a record
    whose strategy_id was flipped after construction is rejected.
    """
    if not isinstance(rec, dict):
        raise SignalValidationError("signal record is not an object")

    for field in REQUIRED_PROVENANCE:
        value = rec.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            raise SignalValidationError(f"missing required provenance field: {field}")

    if rec["schema_version"] != SCHEMA_VERSION:
        raise SignalValidationError(
            f"unsupported schema_version {rec['schema_version']!r}; expected {SCHEMA_VERSION!r}"
        )
    if rec["strategy_id"] not in STRATEGY_IDS:
        raise SignalValidationError(f"unknown strategy_id: {rec['strategy_id']!r}")
    if expected_strategy_id is not None and rec["strategy_id"] != expected_strategy_id:
        raise SignalValidationError(
            f"strategy relabel detected: record is {rec['strategy_id']}, "
            f"expected {expected_strategy_id}"
        )
    if not rec["idempotency_key"].startswith(f"{rec['strategy_id']}:"):
        raise SignalValidationError(
            "idempotency_key does not embed the record's strategy_id; "
            "the key and the strategy label disagree"
        )
    if rec["environment"] not in ENVIRONMENTS:
        raise SignalValidationError(f"environment must be SIM/PAPER/TEST, got {rec['environment']!r}")

    cls = rec.get("classification") or {}
    if cls.get("classification") not in CLASSIFICATIONS:
        raise SignalValidationError(
            f"classification must be one of {CLASSIFICATIONS}, got {cls.get('classification')!r}"
        )
    if not cls.get("qualification_status"):
        raise SignalValidationError("classification.qualification_status is required")

    # Market-state numeric sanity (finding F-2): the Strategy A adapter
    # path previously recorded alert prices of -100.0 and even the string
    # "twenty-six thousand" as qualified signals, because validation
    # checked provenance and risk fields but never the numbers. Every
    # present price/indicator value must now be a real, finite number,
    # and every price must be > 0. This runs on EVERY record — both
    # adapters construct through new_signal_record and the store
    # re-validates at insert — so no adapter path can persist a record
    # whose numbers were never sanity-checked.
    ms = rec.get("market_state") or {}
    _check_numeric("market_state.price", ms.get("price"), price=True)
    vwap = ms.get("vwap")
    if isinstance(vwap, dict):
        _check_numeric("market_state.vwap.value", vwap.get("value"), price=True)
    else:
        _check_numeric("market_state.vwap", vwap, price=True)
    _check_numeric("market_state.ema9", ms.get("ema9"), price=True)
    _check_numeric("market_state.ema21", ms.get("ema21"), price=True)
    _check_numeric("market_state.rsi14", ms.get("rsi14"))
    _check_numeric("market_state.range_high", ms.get("range_high"), price=True)
    _check_numeric("market_state.range_low", ms.get("range_low"), price=True)
    _check_numeric(
        "market_state.confirmed_sr_level", ms.get("confirmed_sr_level"), price=True
    )

    risk = rec.get("risk") or {}
    approval = risk.get("risk_approval_status")
    if approval not in (RISK_APPROVED, RISK_UNAPPROVED):
        raise SignalValidationError(
            f"risk.risk_approval_status must be APPROVED or UNAPPROVED, got {approval!r}"
        )
    if approval != RISK_APPROVED:
        for field in _ORDER_FIELDS_WHEN_UNAPPROVED:
            if risk.get(field) is not None:
                raise SignalValidationError(
                    f"invented risk rejected: risk.{field} is populated while "
                    f"risk_approval_status is {approval}; no approved dollar-risk "
                    "rule exists, so quantity/target/exposure must stay empty"
                )
    if risk.get("reward_risk") is not None and risk.get("target") is None:
        raise SignalValidationError(
            "risk.reward_risk is populated without a target; R/R cannot be "
            "computed or claimed without an approved exit framework"
        )
    # Risk numeric sanity (finding F-2): entry/stop/target are prices
    # and obey the same rule as market-state prices; a stop distance is
    # a derived magnitude and may be zero but never negative or textual.
    _check_numeric("risk.proposed_entry", risk.get("proposed_entry"), price=True)
    _check_numeric("risk.structural_stop", risk.get("structural_stop"), price=True)
    _check_numeric("risk.target", risk.get("target"), price=True)
    _check_numeric("risk.reward_risk", risk.get("reward_risk"))
    stop_distance = risk.get("stop_distance_points")
    _check_numeric("risk.stop_distance_points", stop_distance)
    if stop_distance is not None and stop_distance < 0:
        raise SignalValidationError(
            f"risk.stop_distance_points must be >= 0, got {stop_distance!r}"
        )

    ai = rec.get("ai_explanation") or {}
    if ai.get("explanation_source") not in (EXPLANATION_SOURCE_FALLBACK, EXPLANATION_SOURCE_LIVE):
        raise SignalValidationError(
            "ai_explanation.explanation_source must declare live provider or "
            "deterministic fallback"
        )
    return rec


def to_json(rec: Dict[str, Any]) -> str:
    """Serialize a validated record deterministically (sorted keys)."""
    validate_signal_record(rec)
    return json.dumps(rec, sort_keys=True, ensure_ascii=False)


def from_json(payload: str) -> Dict[str, Any]:
    """Parse and validate a serialized record."""
    return validate_signal_record(json.loads(payload))
