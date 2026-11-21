"""Bot B — Outer Range Extremes signal detector (SIM / PAPER / TEST only).

Layered on the existing Strategy B evaluator
(``strategy_engine.evaluate_strategy_b``). Bot B adds, per the Bot B Master
Development Prompt v1.0 (founder, Nov 15, 2026) and
``docs/strategies/BOT_B_DETECTOR_SPEC.md``:

- the five-state classification: WAITING / POTENTIAL SETUP /
  CONFIRMATION PENDING / VALIDATED PAPER SIGNAL / NO TRADE;
- the full explanation record (prompt section 4) for every evaluation;
- a paper-trade record for VALIDATED PAPER SIGNALs only — a simulated fill
  for the Dashboard's own PAPER journal. It is data, not an order: this
  module performs no network calls, places no orders, and connects to no
  execution endpoint;
- a detector with an append-only audit trail and duplicate suppression.

Governance (approved Strategy B, MQU-SB-001 v1.0, governs over the prompt
draft wherever they differ — see the spec's Ambiguity Register):

- The 15m range must be supplied; it is never invented (Rule 1).
- Confirmation engulfing is governed by the 15m bar (A-1 interim); the 5m
  engulfing state is reported in the record.
- EMA9 is reported as context only and never gates (A-2 interim).
- VWAP position is reported in every record; there is no hard VWAP veto
  beyond the approved rules (A-3 interim). VWAP still participates exactly
  as the approved evaluator uses it — inside timeframe alignment (Rule 4).
- No numeric parameter is invented: no near-zone width, no volume
  threshold, no risk limit, no exit framework. POTENTIAL SETUP uses only
  the evaluator's own midpoint convention plus the direction of the last
  two closes (data, not a parameter).
- A VALIDATED PAPER SIGNAL is impossible unless the underlying evaluator
  fires, which itself requires STRATEGY_B_PARAMETERS_APPROVED plus a
  supplied range, risk limit, and exit conditions.
"""
from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from zoneinfo import ZoneInfo

from strategy_engine import (
    aggregate_bars,
    bearish_engulfing,
    bullish_engulfing,
    ema_series,
    evaluate_strategy_b,
    rsi_last,
    snapshot_freshness,
    vwap_series,
)
from strategy_rules import STRATEGY_B_PLACEHOLDERS, pending_keys

ET = ZoneInfo("America/New_York")

CLASSIFICATIONS = (
    "WAITING",
    "POTENTIAL SETUP",
    "CONFIRMATION PENDING",
    "VALIDATED PAPER SIGNAL",
    "NO TRADE",
)

_RULE_LABELS = {
    "R1": "R1 15m range supplied and valid",
    "R2": "R2 price at a range extreme (never mid-range)",
    "R3": "R3 engulfing confirmation at the boundary (15m)",
    "R4": "R4 15m/5m/1m framework aligned (EMA 21 + VWAP supporting)",
    "R5": "R5 indicators supporting only, never a setup alone",
    "R6": "R6 structural invalidation + dollar risk inside the supplied limit",
    "R7": "R7 exit conditions defined before entry",
}


def _is_num(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _bars_error(bars: Any) -> Optional[str]:
    """None if usable; a reason string if the bars are malformed."""
    if bars is None:
        return None  # treated as "no data yet" by the caller
    if not isinstance(bars, (list, tuple)):
        return "bars payload is not a list"
    for b in bars:
        if not isinstance(b, dict):
            return "a bar is not an object"
        for field in ("time", "open", "high", "low", "close"):
            if not _is_num(b.get(field)):
                return f"bar field '{field}' is missing or not a finite number"
        if b["high"] < b["low"]:
            return "bar high is below its low"
    return None


def _engulfing_flags(bars_tf: Sequence[Dict[str, Any]]) -> Dict[str, Optional[bool]]:
    if len(bars_tf) < 2:
        return {"bullish": None, "bearish": None}
    prev, cur = bars_tf[-2], bars_tf[-1]
    return {"bullish": bullish_engulfing(prev, cur), "bearish": bearish_engulfing(prev, cur)}


def _base_record(now: datetime) -> Dict[str, Any]:
    return {
        "bot": "Bot B",
        "instrument": "MNQ",
        "strategy": "Outer Range Extremes",
        "timestamp": now.astimezone(ET).isoformat(),
        "timezone": "America/New_York",
        "classification": "WAITING",
        "direction": None,
        "range": {"high": None, "low": None},
        "price": None,
        "bar_time": None,
        "confirmation_5m": "not evaluated",
        "entry_1m": "not evaluated",
        "engulfing": {"tf_15m": {"bullish": None, "bearish": None},
                      "tf_5m": {"bullish": None, "bearish": None},
                      "governing_timeframe": "15m (approved rules; A-1 interim)"},
        "ema": {"ema9_5m": None, "ema21_5m": None,
                "note": "EMA9 is context only and never gates (A-2 interim)"},
        "vwap": {"value_5m": None, "position": None,
                 "note": "reported always; no hard veto beyond the approved rules (A-3 interim)"},
        "rsi14_5m": None,
        "volume": {"last_bar": None,
                   "status": "informational only — no approved volume threshold (A-5)"},
        "conditions_passed": [],
        "conditions_failed": [],
        "parameters_pending": [],
        "data_label": "delayed",
        "explanation": "",
        "paper_trade": None,
        "evaluator": None,
    }


def evaluate_bot_b(
    bars_1m: Optional[Sequence[Dict[str, Any]]],
    *,
    range_high: Optional[float] = None,
    range_low: Optional[float] = None,
    risk_limit_dollars: Optional[float] = None,
    exit_conditions: Optional[str] = None,
    approved: Optional[bool] = None,
    snapshot: Optional[Dict[str, Any]] = None,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Evaluate one Bot B classification from 1m bars. Pure; no I/O."""
    now = now or datetime.now(timezone.utc)
    rec = _base_record(now)
    rec["range"] = {"high": range_high, "low": range_low}

    err = _bars_error(bars_1m)
    if err is not None:
        rec["classification"] = "NO TRADE"
        rec["conditions_failed"] = [f"data rejected: {err}"]
        rec["explanation"] = f"Market data was rejected as malformed ({err}). No evaluation was performed and nothing was fabricated."
        return rec

    bars: List[Dict[str, Any]] = list(bars_1m or [])
    if not bars:
        rec["explanation"] = "No market data has been received yet. Bot B is waiting — it does not manufacture a signal from missing data."
        return rec

    last = bars[-1]
    rec["price"] = last["close"]
    rec["bar_time"] = last["time"]
    rec["volume"]["last_bar"] = last.get("volume")

    # Fail-closed data gate, the platform standard (PR #21): a supplied
    # snapshot must carry a fresh, parseable timestamp.
    if snapshot is not None:
        fresh, reason = snapshot_freshness(snapshot, now)
        if not fresh:
            rec["classification"] = "NO TRADE"
            rec["conditions_failed"] = [f"data rejected: snapshot {reason}"]
            rec["explanation"] = f"Market data was rejected before evaluation ({reason}). Stale, incomplete, or malformed data never produces a signal."
            return rec
        if snapshot.get("data_label"):
            rec["data_label"] = snapshot["data_label"]
        if snapshot.get("symbol"):
            rec["instrument"] = snapshot["symbol"]

    # Confirmation-context indicators on the 5m chart (reported, per prompt s.4).
    bars_15 = aggregate_bars(bars, 15 * 60)
    bars_5 = aggregate_bars(bars, 5 * 60)
    closes_5 = [b["close"] for b in bars_5]
    e9 = ema_series(closes_5, 9)
    e21 = ema_series(closes_5, 21)
    vw = vwap_series(bars_5)
    rec["ema"]["ema9_5m"] = round(e9[-1], 2) if e9 and e9[-1] is not None else None
    rec["ema"]["ema21_5m"] = round(e21[-1], 2) if e21 and e21[-1] is not None else None
    if vw and vw[-1] is not None:
        rec["vwap"]["value_5m"] = round(vw[-1], 2)
        rec["vwap"]["position"] = "price above VWAP" if last["close"] >= vw[-1] else "price below VWAP"
    rec["rsi14_5m"] = rsi_last(closes_5, 14)
    rec["engulfing"]["tf_15m"] = _engulfing_flags(bars_15)
    rec["engulfing"]["tf_5m"] = _engulfing_flags(bars_5)

    # Range gate (Rule 1): supplied, never invented.
    if range_high is None or range_low is None:
        rec["parameters_pending"] = pending_keys(
            STRATEGY_B_PLACEHOLDERS,
            {"range_high": range_high, "range_low": range_low,
             "risk_limit_dollars": risk_limit_dollars,
             "engulfing_validity_window_bars": None},
        )
        rec["conditions_failed"] = ["R1: the 15m range high/low were not supplied — Bot B will not invent a range"]
        rec["explanation"] = "Waiting: no 15m range has been supplied, and Bot B never invents one. Supply the established range high and low to begin evaluation."
        return rec
    if range_high <= range_low:
        rec["classification"] = "NO TRADE"
        rec["conditions_failed"] = ["R1: invalid range (high must be above low)"]
        rec["explanation"] = f"No trade: the supplied range is invalid (high {range_high} must be above low {range_low})."
        return rec

    ev = evaluate_strategy_b(
        bars,
        range_high=range_high,
        range_low=range_low,
        risk_limit_dollars=risk_limit_dollars,
        approved=approved,
        snapshot=snapshot,
        exit_conditions=exit_conditions,
    )
    rec["evaluator"] = ev
    rules: Dict[str, Any] = ev.get("rules") or {}
    rec["conditions_passed"] = [_RULE_LABELS[k] for k in sorted(rules) if rules[k]]
    rec["conditions_failed"] = [_RULE_LABELS[k] for k in sorted(rules) if not rules[k]]
    rec["parameters_pending"] = ev.get("parameters_pending") or rec["parameters_pending"]
    direction = ev.get("direction") if ev.get("direction") in ("LONG", "SHORT") else None

    tfs = ev.get("timeframes") or {}
    if "5m" in tfs:
        rec["confirmation_5m"] = "aligned" if tfs["5m"].get("ok") else f"not aligned — {tfs['5m'].get('reason')}"
    if "1m" in tfs:
        rec["entry_1m"] = "aligned" if tfs["1m"].get("ok") else f"not aligned — {tfs['1m'].get('reason')}"

    mid = (range_high + range_low) / 2
    price = last["close"]

    if ev.get("fire") and ev.get("state") == "CONFIRMED":
        rec["classification"] = "VALIDATED PAPER SIGNAL"
        rec["direction"] = direction
        rec["paper_trade"] = {
            "action": "BUY" if direction == "LONG" else "SELL",
            "symbol": rec["instrument"],
            "side": "long" if direction == "LONG" else "short",
            "entry_price": price,
            "invalidation": ev.get("invalidation"),
            "dollar_risk_per_contract": ev.get("dollar_risk_per_contract"),
            "exit_conditions": exit_conditions,
            "data_label": "PAPER",
            "classification": "VALIDATED PAPER SIGNAL",
            "timestamp": rec["timestamp"],
        }
        rec["explanation"] = (
            f"Validated paper signal ({direction}): price {price} is at the "
            f"{'lower' if direction == 'LONG' else 'upper'} boundary of the supplied 15m range "
            f"{range_low}–{range_high}, with engulfing confirmation on the 15m bar and the 5m and 1m "
            f"charts aligned. Structural risk is ${ev.get('dollar_risk_per_contract')} per contract "
            f"against the supplied limit. This is a PAPER record for education and testing — no order exists."
        )
        return rec

    if ev.get("state") == "DISABLED_PENDING_PARAMETERS":
        rec["classification"] = "CONFIRMATION PENDING"
        rec["direction"] = direction
        rec["explanation"] = (
            "Every documented Strategy B rule passed on this data, but the Strategy B parameters are "
            "not founder-approved (STRATEGY_B_PARAMETERS_APPROVED is not set), so Bot B records this as "
            "CONFIRMATION PENDING — never as a validated signal."
        )
        return rec

    if rules.get("R2") is False:
        # Not at an extreme. POTENTIAL SETUP only when price sits in a
        # boundary half AND the last close moved toward that boundary
        # (evaluator midpoint convention + direction of travel; no
        # invented zone width).
        bar15 = bars_15[-1] if bars_15 else last
        touched_both = bar15["high"] >= range_high and bar15["low"] <= range_low
        prev_close = bars[-2]["close"] if len(bars) >= 2 else price
        if touched_both:
            rec["explanation"] = "Waiting: the current 15m bar spans both boundaries — a mixed picture, and Bot B does not initiate in confusion."
        elif price > mid and (range_high - price) < (range_high - prev_close):
            rec["classification"] = "POTENTIAL SETUP"
            rec["direction"] = "SHORT"
            rec["explanation"] = f"Potential setup: price {price} is in the upper half of the range {range_low}–{range_high} and moving toward the upper boundary. No setup exists until price interacts with the boundary and confirms."
        elif price < mid and (price - range_low) < (prev_close - range_low):
            rec["classification"] = "POTENTIAL SETUP"
            rec["direction"] = "LONG"
            rec["explanation"] = f"Potential setup: price {price} is in the lower half of the range {range_low}–{range_high} and moving toward the lower boundary. No setup exists until price interacts with the boundary and confirms."
        else:
            rec["explanation"] = f"Waiting: price {price} is mid-range ({range_low}–{range_high}) or moving away from the boundaries. Strategy B never initiates in the middle."
        return rec

    if rules.get("R3") is False:
        rec["classification"] = "CONFIRMATION PENDING"
        rec["direction"] = direction
        rec["explanation"] = (
            f"Confirmation pending: price is at a range boundary, but no qualifying engulfing candle has "
            f"confirmed on the 15m chart (a single wick is not sufficient). Bot B waits for the completed confirmation."
        )
        return rec

    if rules.get("R4") is False:
        rec["classification"] = "NO TRADE"
        rec["direction"] = direction
        rec["conditions_failed"] = rec["conditions_failed"] or [_RULE_LABELS["R4"]]
        rec["explanation"] = (
            f"No trade: the three-chart framework is in conflict ({ev.get('trigger')}). "
            "Contradictory confirmations are rejected — conflict means WAIT, and a failed mandatory condition means NO TRADE."
        )
        return rec

    if rules.get("R6") is False:
        if risk_limit_dollars is None:
            rec["classification"] = "CONFIRMATION PENDING"
            rec["direction"] = direction
            if "risk_limit_dollars" not in rec["parameters_pending"]:
                rec["parameters_pending"] = [*rec["parameters_pending"], "risk_limit_dollars"]
            rec["explanation"] = "Confirmation pending: structure and confirmation are in place, but no dollar risk limit has been supplied, and Bot B will not invent one (Rule 6)."
        else:
            rec["classification"] = "NO TRADE"
            rec["direction"] = direction
            rec["explanation"] = f"No trade: the structural stop exceeds the supplied risk limit ({ev.get('trigger')}). Risk before entry — the setup is rejected, not resized."
        return rec

    if rules.get("R7") is False:
        rec["classification"] = "CONFIRMATION PENDING"
        rec["direction"] = direction
        rec["explanation"] = "Confirmation pending: exit conditions have not been defined, and Rule 7 requires them before any entry. Bot B will not invent an exit framework."
        return rec

    rec["explanation"] = f"Waiting: evaluation completed without a classification edge ({ev.get('trigger')})."
    return rec


def evaluation_key(rec: Dict[str, Any]) -> Any:
    """Event identity for duplicate suppression: same bar, same verdict."""
    return (
        rec.get("classification"),
        rec.get("direction"),
        rec.get("bar_time"),
        (rec.get("range") or {}).get("high"),
        (rec.get("range") or {}).get("low"),
    )


class BotBDetector:
    """Stateful detector: evaluates new bars, keeps an audit trail, and
    suppresses duplicate classifications of the same bar."""

    def __init__(self, audit_path: Optional[str] = None):
        self.audit_path = audit_path
        self.records: List[Dict[str, Any]] = []
        self._last_key: Any = None

    def evaluate(self, bars_1m: Optional[Sequence[Dict[str, Any]]], **kwargs: Any) -> Dict[str, Any]:
        rec = evaluate_bot_b(bars_1m, **kwargs)
        key = evaluation_key(rec)
        rec["duplicate"] = key == self._last_key
        self._last_key = key
        if not rec["duplicate"]:
            self.records.append(rec)
            if self.audit_path:
                with open(self.audit_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(rec) + "\n")
        return rec
