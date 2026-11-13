"""Alerts-only evaluators for the Alerts panel, Strategy A (Six Gates), and Strategy B (Outer Range).

No broker execution. Yahoo data is delayed. Confirmation alerts for A/B stay
disabled until the founder approves PENDING parameters.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence

from strategy_rules import (
    MNQ_DOLLARS_PER_POINT,
    STRATEGY_A_PLACEHOLDERS,
    STRATEGY_B_PLACEHOLDERS,
    pending_keys,
    strategy_a_approved,
    strategy_a_params,
    strategy_b_approved,
)

StrategyResult = Dict[str, Any]


def aggregate_bars(bars: Sequence[Dict[str, Any]], tf_seconds: int) -> List[Dict[str, Any]]:
    if tf_seconds <= 60:
        return list(bars)
    bucket: Dict[int, Dict[str, Any]] = {}
    for b in bars:
        slot = int(b["time"] // tf_seconds) * tf_seconds
        cur = bucket.get(slot)
        if cur is None:
            bucket[slot] = {
                "time": slot, "open": b["open"], "high": b["high"],
                "low": b["low"], "close": b["close"], "volume": b.get("volume") or 0,
            }
        else:
            cur["high"] = max(cur["high"], b["high"])
            cur["low"] = min(cur["low"], b["low"])
            cur["close"] = b["close"]
            cur["volume"] += b.get("volume") or 0
    return [bucket[k] for k in sorted(bucket)]


def ema_series(closes: Sequence[float], period: int) -> List[Optional[float]]:
    if len(closes) < period:
        return [None] * len(closes)
    k = 2 / (period + 1)
    out: List[Optional[float]] = [None] * (period - 1)
    seed = sum(closes[:period]) / period
    out.append(seed)
    for c in closes[period:]:
        seed = c * k + seed * (1 - k)
        out.append(seed)
    return out


def vwap_series(bars: Sequence[Dict[str, Any]]) -> List[Optional[float]]:
    cum_pv = cum_v = 0.0
    out: List[Optional[float]] = []
    for b in bars:
        typ = (b["high"] + b["low"] + b["close"]) / 3
        vol = b.get("volume") or 1
        cum_pv += typ * vol
        cum_v += vol
        out.append((cum_pv / cum_v) if cum_v else None)
    return out


def rsi_last(closes: Sequence[float], period: int = 14) -> Optional[float]:
    if len(closes) < period + 1:
        return None
    gains = losses = 0.0
    for i in range(-period, 0):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_g, avg_l = gains / period, losses / period
    if avg_l == 0:
        return 100.0 if avg_g > 0 else 50.0
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def last_completed(bars: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    return dict(bars[-1]) if bars else None


def timeframe_alignment(bars_tf: Sequence[Dict[str, Any]], ema_slow: int, direction: str) -> Dict[str, Any]:
    """Direction is close vs EMA 21 AND VWAP (both must agree). Labels use EMA 21 and VWAP."""
    if not bars_tf:
        return {"ok": False, "reason": "no bars", "ema21": None, "vwap": None, "close": None}
    closes = [b["close"] for b in bars_tf]
    e21 = ema_series(closes, ema_slow)
    vw = vwap_series(bars_tf)
    close, ema21, vwap = closes[-1], e21[-1], vw[-1]
    if ema21 is None or vwap is None:
        return {"ok": False, "reason": "indicators not ready", "ema21": ema21, "vwap": vwap, "close": close}
    long_ok = close >= ema21 and close >= vwap
    short_ok = close <= ema21 and close <= vwap
    if direction == "LONG":
        ok = long_ok
    elif direction == "SHORT":
        ok = short_ok
    else:
        ok = False
    return {
        "ok": ok,
        "ema21": round(ema21, 2),
        "vwap": round(vwap, 2),
        "close": close,
        "label": "EMA 21 and VWAP",
        "reason": None if ok else f"close {close} not aligned with EMA 21 {ema21:.2f} and VWAP {vwap:.2f} for {direction}",
    }


def bullish_engulfing(prev: Dict[str, Any], cur: Dict[str, Any]) -> bool:
    """Textbook body-engulfing: current bullish body fully contains previous body. A wick alone is not enough."""
    prev_body_low, prev_body_high = sorted((prev["open"], prev["close"]))
    cur_body_low, cur_body_high = sorted((cur["open"], cur["close"]))
    return cur["close"] > cur["open"] and cur_body_low <= prev_body_low and cur_body_high >= prev_body_high and (cur_body_high - cur_body_low) > (prev_body_high - prev_body_low)


def bearish_engulfing(prev: Dict[str, Any], cur: Dict[str, Any]) -> bool:
    prev_body_low, prev_body_high = sorted((prev["open"], prev["close"]))
    cur_body_low, cur_body_high = sorted((cur["open"], cur["close"]))
    return cur["close"] < cur["open"] and cur_body_low <= prev_body_low and cur_body_high >= prev_body_high and (cur_body_high - cur_body_low) > (prev_body_high - prev_body_low)


def evaluate_panel_alert(alert: Dict[str, Any], snapshot: Dict[str, Any]) -> StrategyResult:
    """User-configured Alerts panel rules: breakout, vwap_cross, price_target, stop_loss."""
    price = snapshot.get("price") or snapshot.get("close")
    vwap = snapshot.get("vwap")
    prev = snapshot.get("previous_close")
    atype = (alert.get("alert_type") or "").lower()
    cond = (alert.get("condition") or "above").lower()
    target = alert.get("target_value")
    symbol = alert.get("symbol") or snapshot.get("symbol") or "MNQ"
    fired = False
    trigger = f"panel {atype} {cond} {target}"
    if price is None:
        return _wait("Alerts panel", "price unavailable", symbol)
    if atype in {"breakout", "price_target", "stop_loss"} and target is not None:
        if cond == "above":
            fired = price >= float(target)
        elif cond == "below":
            fired = price <= float(target)
        trigger = f"{atype}: price {price} {cond} {target}"
    elif atype == "vwap_cross" and vwap is not None and prev is not None:
        if cond == "above":
            fired = prev < vwap <= price
        else:
            fired = prev > vwap >= price
        trigger = f"VWAP cross {cond}: prev {prev}, VWAP {vwap}, price {price}"
    direction = "LONG" if cond == "above" else "SHORT"
    if not fired:
        return {
            "fire": False,
            "state": "WAIT",
            "direction": "WAIT",
            "strategy": f"Alerts panel ({atype})",
            "instrument": symbol,
            "timeframe": "1m entry (panel rule)",
            "trigger": trigger + " — not met",
            "data_label": snapshot.get("data_label") or "delayed",
        }
    return {
        "fire": True,
        "state": "CONFIRMED",
        "direction": direction,
        "strategy": f"Alerts panel ({atype})",
        "instrument": symbol,
        "timeframe": "1m entry (panel rule)",
        "trigger": trigger,
        "data_label": snapshot.get("data_label") or "delayed",
        "alert_id": alert.get("id"),
    }


def evaluate_strategy_a(
    bars_1m: Sequence[Dict[str, Any]],
    *,
    params: Optional[Dict[str, Any]] = None,
    approved: Optional[bool] = None,
    center: float = 0.0,
    es_aligned: Optional[bool] = None,
    snapshot: Optional[Dict[str, Any]] = None,
) -> StrategyResult:
    approved = strategy_a_approved() if approved is None else approved
    p = strategy_a_params(params)
    snap = snapshot or {}
    instrument = snap.get("symbol") or "MNQ"
    label = snap.get("data_label") or "delayed"
    tf = "15m confirmation / 5m bias / 1m entry"
    if not bars_1m:
        return _wait("A Six Gates", "no 1m bars", instrument, tf, label)

    bars_15 = aggregate_bars(bars_1m, 15 * 60)
    bars_5 = aggregate_bars(bars_1m, 5 * 60)
    bar = bars_1m[-1]
    closes = [b["close"] for b in bars_1m]
    ema_fast_p, ema_slow_p = int(p["ema_fast"] or 9), int(p["ema_slow"] or 21)
    e9 = ema_series(closes, ema_fast_p)
    e21 = ema_series(closes, ema_slow_p)
    vw = vwap_series(bars_1m)

    # Gate 3 — completed bar assumed (caller should pass only closed bars).
    gates: Dict[str, Any] = {"G3_candle_close": True}

    # Gate 1 — location
    if not center:
        # prior-day midpoint cannot be inferred from a short 1m buffer without a daily series.
        # Use the provided center only; 0 means "auto prior-day midpoint" in the Pine script,
        # which we cannot reconstruct here — wait rather than invent a level.
        gates["G1_location"] = False
        return {**_wait("A Six Gates", "G1: Center S/R is 0 and prior-day midpoint was not supplied (will not invent a level)", instrument, tf, label), "gates": gates, "indicators": _inds(e9, e21, vw, bar)}

    width = float(p["zone_width_points"] or 0)
    zone_lo, zone_hi = center - width, center + width
    intersects = bar["low"] <= zone_hi and bar["high"] >= zone_lo
    gates["G1_location"] = bool(intersects)
    if not intersects:
        return {**_wait("A Six Gates", f"G1: 1m bar does not intersect center {center} ± {width}", instrument, tf, label), "gates": gates, "indicators": _inds(e9, e21, vw, bar)}

    # Decide candidate direction from close vs center (for activity / alignment).
    direction = "LONG" if bar["close"] >= center else "SHORT"

    # Gate 2 — activity
    vol_len = int(p["volume_sma_length"] or 20)
    vols = [b.get("volume") or 0 for b in bars_1m]
    sma_vol = (sum(vols[-vol_len:]) / vol_len) if len(vols) >= vol_len else None
    rng = max(bar["high"] - bar["low"], 1e-9)
    body = abs(bar["close"] - bar["open"])
    lower_wick = min(bar["open"], bar["close"]) - bar["low"]
    upper_wick = bar["high"] - max(bar["open"], bar["close"])
    vol_ok = sma_vol is not None and bar.get("volume", 0) >= sma_vol * float(p["volume_spike_multiple"] or 0)
    wick_ok = (lower_wick / rng >= float(p["rejection_wick_ratio"] or 0) and direction == "LONG") or (
        upper_wick / rng >= float(p["rejection_wick_ratio"] or 0) and direction == "SHORT"
    )
    body_ok = body / rng >= float(p["strong_body_ratio"] or 0) and (
        (direction == "LONG" and bar["close"] > bar["open"]) or (direction == "SHORT" and bar["close"] < bar["open"])
    )
    gates["G2_activity"] = bool(vol_ok or wick_ok or body_ok)
    if not gates["G2_activity"]:
        return {**_wait("A Six Gates", "G2: no volume spike, rejection wick, or strong-body bar", instrument, tf, label, direction), "gates": gates, "indicators": _inds(e9, e21, vw, bar)}

    # Gate 4 — retest / no-chase
    lookback = int(p["left_zone_lookback"] or 10)
    window = bars_1m[-(lookback + 1):-1]
    left = any(b["high"] < zone_lo or b["low"] > zone_hi for b in window)
    returned = intersects
    held = (bar["close"] > center) if direction == "LONG" else (bar["close"] < center)
    atr = _atr(bars_1m, int(p["atr_length"] or 14))
    no_chase_range = atr is not None and rng <= atr * float(p["no_chase_atr_k"] or 0)
    ema9 = e9[-1]
    no_chase_ema = ema9 is not None and abs(bar["close"] - ema9) <= float(p["no_chase_ema9_max_points"] or 0)
    gates["G4_retest_no_chase"] = bool(left and returned and held and no_chase_range and no_chase_ema)
    if not gates["G4_retest_no_chase"]:
        return {**_wait("A Six Gates", "G4: retest/no-chase not met (left zone, return, hold, ATR, EMA 9 distance)", instrument, tf, label, direction), "gates": gates, "indicators": _inds(e9, e21, vw, bar)}

    # Gate 5 — 15m then 5m then 1m alignment (EMA 21 + VWAP)
    a15 = timeframe_alignment(bars_15, ema_slow_p, direction)
    a5 = timeframe_alignment(bars_5, ema_slow_p, direction)
    a1 = timeframe_alignment(bars_1m, ema_slow_p, direction)
    mnq_ok = a15["ok"] and a5["ok"] and a1["ok"]
    rsi = rsi_last(closes, int(p["rsi_length"] or 14))
    extra = False
    if mnq_ok and es_aligned is False:
        extra = (direction == "LONG" and rsi is not None and rsi > float(p["rsi_long_extra"])) or (
            direction == "SHORT" and rsi is not None and rsi < float(p["rsi_short_extra"])
        )
        gates["G5_alignment"] = extra
        gates["G5_path"] = "PASS*" if extra else "FAIL (ES divergence, RSI extra evidence not met)"
    else:
        # es_aligned is None (ES not supplied) or True
        gates["G5_alignment"] = mnq_ok and (es_aligned is not False)
        gates["G5_path"] = "PASS" if gates["G5_alignment"] else "FAIL (15m/5m/1m EMA 21 + VWAP)"
    if not gates["G5_alignment"]:
        reason = f"G5: {gates['G5_path']}; 15m={a15['reason']}; 5m={a5['reason']}; 1m={a1['reason']}"
        return {**_wait("A Six Gates", reason, instrument, tf, label, direction), "gates": gates, "timeframes": {"15m": a15, "5m": a5, "1m": a1}, "indicators": _inds(e9, e21, vw, bar)}

    # Hard VWAP rule
    vwap_now = vw[-1]
    if vwap_now is not None:
        if direction == "LONG" and bar["close"] < vwap_now:
            gates["hard_vwap"] = False
            return {**_wait("A Six Gates", "hard VWAP rule: no LONG when close < VWAP", instrument, tf, label, direction), "gates": gates, "indicators": _inds(e9, e21, vw, bar)}
        if direction == "SHORT" and bar["close"] > vwap_now:
            gates["hard_vwap"] = False
            return {**_wait("A Six Gates", "hard VWAP rule: no SHORT when close > VWAP", instrument, tf, label, direction), "gates": gates, "indicators": _inds(e9, e21, vw, bar)}
    gates["hard_vwap"] = True

    # Gate 6 — risk
    swing_n = lookback
    window_incl = bars_1m[-swing_n:] if len(bars_1m) >= swing_n else bars_1m
    invalidation = min(b["low"] for b in window_incl) if direction == "LONG" else max(b["high"] for b in window_incl)
    stop_dist = abs(bar["close"] - invalidation)
    max_risk = p.get("max_risk_points")
    if max_risk is None:
        gates["G6_risk"] = False
        return {**_wait("A Six Gates", "G6: max_risk_points is PENDING (no silent default) — WAIT", instrument, tf, label, direction), "gates": gates, "indicators": _inds(e9, e21, vw, bar), "parameters_pending": ["max_risk_points"]}
    gates["G6_risk"] = 0 < stop_dist <= float(max_risk)
    if not gates["G6_risk"]:
        return {**_wait("A Six Gates", f"G6: stop distance {stop_dist:.2f} not in (0, {max_risk}]", instrument, tf, label, direction), "gates": gates, "indicators": _inds(e9, e21, vw, bar)}

    if not approved:
        return {
            **_wait("A Six Gates", "all documented gates passed on this fixture, but STRATEGY_A_PARAMETERS_APPROVED is not set — confirmation alerts disabled (placeholders PENDING)", instrument, tf, label, direction),
            "gates": gates,
            "state": "DISABLED_PENDING_PARAMETERS",
            "fire": False,
            "preview": True,
            "indicators": _inds(e9, e21, vw, bar),
            "timeframes": {"15m": a15, "5m": a5, "1m": a1},
        }

    trigger = (
        f"G1 location at center {center} ± {width}; G2 activity; G3 completed 1m bar; "
        f"G4 retest/no-chase; G5 15m/5m/1m EMA 21 + VWAP ({gates.get('G5_path')}); "
        f"G6 stop {stop_dist:.2f} pts; hard VWAP rule held"
    )
    return {
        "fire": True,
        "state": "CONFIRMED",
        "direction": direction,
        "strategy": "A Six Gates",
        "instrument": instrument,
        "timeframe": tf,
        "trigger": trigger,
        "data_label": label,
        "gates": gates,
        "indicators": _inds(e9, e21, vw, bar),
        "timeframes": {"15m": a15, "5m": a5, "1m": a1},
        "invalidation": invalidation,
    }


def evaluate_strategy_b(
    bars_1m: Sequence[Dict[str, Any]],
    *,
    range_high: Optional[float] = None,
    range_low: Optional[float] = None,
    risk_limit_dollars: Optional[float] = None,
    approved: Optional[bool] = None,
    snapshot: Optional[Dict[str, Any]] = None,
    exit_conditions: Optional[str] = None,
) -> StrategyResult:
    approved = strategy_b_approved() if approved is None else approved
    snap = snapshot or {}
    instrument = snap.get("symbol") or "MNQ"
    label = snap.get("data_label") or "delayed"
    tf = "15m confirmation / 5m bias / 1m entry"
    rules: Dict[str, Any] = {}

    if range_high is None or range_low is None:
        rules["R1"] = False
        return {**_wait("B Outer Range Extremes", "R1: 15m range high/low were not supplied — will not invent a range", instrument, tf, label), "rules": rules, "parameters_pending": pending_keys(STRATEGY_B_PLACEHOLDERS, {"range_high": range_high, "range_low": range_low, "risk_limit_dollars": risk_limit_dollars, "engulfing_validity_window_bars": None})}

    if range_high <= range_low:
        return {**_wait("B Outer Range Extremes", "R1: invalid range (high must be above low)", instrument, tf, label), "rules": {"R1": False}}

    rules["R1"] = True
    if not bars_1m:
        return {**_wait("B Outer Range Extremes", "no 1m bars", instrument, tf, label), "rules": rules}

    bars_15 = aggregate_bars(bars_1m, 15 * 60)
    bars_5 = aggregate_bars(bars_1m, 5 * 60)
    bar = (bars_15[-1] if bars_15 else bars_1m[-1])
    price = bar["close"]
    mid = (range_high + range_low) / 2
    # Mid-range is WAIT. "At extremes" means closer to a boundary than to mid, and
    # interacting with that boundary (bar range touches the level). No numeric
    # "near zone" width is applied unless later approved — we only use the
    # supplied levels themselves.
    at_upper = bar["high"] >= range_high and price >= mid
    at_lower = bar["low"] <= range_low and price <= mid
    if at_upper and not at_lower:
        direction = "SHORT"
        rules["R2"] = True
    elif at_lower and not at_upper:
        direction = "LONG"
        rules["R2"] = True
    else:
        rules["R2"] = False
        return {**_wait("B Outer Range Extremes", "R2: price is not at a supplied 15m range extreme — WAIT (middle or mixed)", instrument, tf, label), "rules": rules}

    # R3 engulfing at the boundary on the 15m confirmation bar
    if len(bars_15) < 2:
        rules["R3"] = False
        return {**_wait("B Outer Range Extremes", "R3: need at least two 15m bars for engulfing confirmation", instrument, tf, label, direction), "rules": rules}
    prev15, cur15 = bars_15[-2], bars_15[-1]
    engulf = bullish_engulfing(prev15, cur15) if direction == "LONG" else bearish_engulfing(prev15, cur15)
    rules["R3"] = bool(engulf)
    if not engulf:
        return {**_wait("B Outer Range Extremes", "R3: no engulfing confirmation at the boundary (a single wick is not sufficient)", instrument, tf, label, direction), "rules": rules}

    # R4 three-chart: 15m already confirmed; 5m bias close vs EMA 21; 1m refinement same direction
    a5 = timeframe_alignment(bars_5, 21, direction)
    a1 = timeframe_alignment(bars_1m, 21, direction)
    rules["R4"] = bool(a5["ok"] and a1["ok"])
    if not rules["R4"]:
        return {**_wait("B Outer Range Extremes", f"R4: 5m/1m conflict or not aligned ({a5.get('reason')}; {a1.get('reason')}) — WAIT", instrument, tf, label, direction), "rules": rules, "timeframes": {"5m": a5, "1m": a1}}

    # R5 — indicators are supporting evidence only; already required alongside structure, not alone.
    rules["R5"] = True

    # R6 risk
    window = bars_1m[-20:] if len(bars_1m) >= 20 else list(bars_1m)
    invalidation = min(b["low"] for b in window) if direction == "LONG" else max(b["high"] for b in window)
    stop_dist = abs(bars_1m[-1]["close"] - invalidation)
    dollar_risk = stop_dist * MNQ_DOLLARS_PER_POINT
    if risk_limit_dollars is None:
        rules["R6"] = False
        return {**_wait("B Outer Range Extremes", "R6: risk_limit_dollars is PENDING — WAIT (will not invent a risk cap)", instrument, tf, label, direction), "rules": rules, "parameters_pending": ["risk_limit_dollars"], "dollar_risk_per_contract": dollar_risk}

    if dollar_risk > float(risk_limit_dollars):
        rules["R6"] = False
        return {**_wait("B Outer Range Extremes", f"R6: structural stop ${dollar_risk:.2f} exceeds risk limit ${float(risk_limit_dollars):.2f} — WAIT", instrument, tf, label, direction), "rules": rules, "dollar_risk_per_contract": dollar_risk}
    rules["R6"] = True

    # R7 — exit conditions must be stated; we do not invent an exit framework.
    if not exit_conditions:
        rules["R7"] = False
        return {**_wait("B Outer Range Extremes", "R7: exit conditions were not defined before alert — WAIT (will not invent an exit framework)", instrument, tf, label, direction), "rules": rules}
    rules["R7"] = True

    if not approved:
        return {
            **_wait("B Outer Range Extremes", "documented rules passed on this fixture, but STRATEGY_B_PARAMETERS_APPROVED is not set — confirmation alerts disabled (placeholders PENDING)", instrument, tf, label, direction),
            "rules": rules,
            "state": "DISABLED_PENDING_PARAMETERS",
            "fire": False,
            "preview": True,
            "timeframes": {"5m": a5, "1m": a1},
        }

    trigger = (
        f"R1 15m range {range_low}–{range_high}; R2 {direction} at extreme; R3 engulfing; "
        f"R4 15m/5m/1m aligned (EMA 21 + VWAP supporting); R5 indicators not used alone; "
        f"R6 stop {stop_dist:.2f} pts (${dollar_risk:.2f}/contract); R7 exits: {exit_conditions}"
    )
    return {
        "fire": True,
        "state": "CONFIRMED",
        "direction": direction,
        "strategy": "B Outer Range Extremes",
        "instrument": instrument,
        "timeframe": tf,
        "trigger": trigger,
        "data_label": label,
        "rules": rules,
        "timeframes": {"5m": a5, "1m": a1, "15m_context": "range + engulfing"},
        "invalidation": invalidation,
        "dollar_risk_per_contract": dollar_risk,
    }


def engine_status() -> Dict[str, Any]:
    return {
        "legacy_ema_cross_engine": "still scheduled separately; it is NOT Strategy A or Strategy B",
        "alerts_panel_evaluator": "enabled",
        "strategy_a": {
            "name": "A Six Gates",
            "parameters_approved": strategy_a_approved(),
            "confirmation_alerts": "enabled" if strategy_a_approved() else "disabled_pending_parameters",
            "pending_placeholders": [k for k, v in STRATEGY_A_PLACEHOLDERS.items() if v["status"] == "PENDING"],
        },
        "strategy_b": {
            "name": "B Outer Range Extremes",
            "parameters_approved": strategy_b_approved(),
            "confirmation_alerts": "enabled" if strategy_b_approved() else "disabled_pending_parameters",
            "pending_placeholders": [k for k, v in STRATEGY_B_PLACEHOLDERS.items() if v["status"] == "PENDING"],
            "seven_rules_documented": True,
        },
        "execution": "alerts only — no orders are placed",
        "data_note": "Yahoo NQ=F is delayed; live label is reserved for licensed TradingView real-time.",
    }


def _atr(bars: Sequence[Dict[str, Any]], period: int) -> Optional[float]:
    if len(bars) < period + 1:
        return None
    trs = []
    for i in range(-period, 0):
        high, low, prev_c = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        trs.append(max(high - low, abs(high - prev_c), abs(low - prev_c)))
    return sum(trs) / period


def _inds(e9, e21, vw, bar) -> Dict[str, Any]:
    return {
        "EMA 9": None if e9[-1] is None else round(e9[-1], 2),
        "EMA 21": None if e21[-1] is None else round(e21[-1], 2),
        "VWAP": None if vw[-1] is None else round(vw[-1], 2),
        "close": bar["close"],
    }


def _wait(strategy: str, reason: str, instrument: str, timeframe: str = "n/a", data_label: str = "delayed", direction: str = "WAIT") -> StrategyResult:
    return {
        "fire": False,
        "state": "WAIT",
        "direction": "WAIT",
        "candidate_direction": direction if direction != "WAIT" else None,
        "strategy": strategy,
        "instrument": instrument,
        "timeframe": timeframe,
        "trigger": reason,
        "data_label": data_label,
    }
