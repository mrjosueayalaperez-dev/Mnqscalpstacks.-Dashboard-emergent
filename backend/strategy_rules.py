"""Documented Strategy A / B rules and PENDING placeholders.

Do not invent entry parameters. Placeholders are disabled in production until
Josue sets STRATEGY_A_PARAMETERS_APPROVED / STRATEGY_B_PARAMETERS_APPROVED.
Citations: docs/strategies/STRATEGY_A_SIX_GATES.md and STRATEGY_B_SEVEN_RULES.md.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

# --- Strategy A Six Gates: placeholder defaults from strategy_a_report.md §2 ---
# Status is PENDING until the founder approves them. max_risk_points has no silent default.
STRATEGY_A_PLACEHOLDERS: Dict[str, Dict[str, Any]] = {
    "zone_width_points": {"value": 15.0, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 1"},
    "volume_sma_length": {"value": 20, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 2"},
    "volume_spike_multiple": {"value": 1.5, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 2"},
    "rejection_wick_ratio": {"value": 0.5, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 2"},
    "strong_body_ratio": {"value": 0.6, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 2"},
    "left_zone_lookback": {"value": 10, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 4"},
    "atr_length": {"value": 14, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 4"},
    "no_chase_atr_k": {"value": 1.5, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 4"},
    "no_chase_ema9_max_points": {"value": 20.0, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 4"},
    "rsi_length": {"value": 14, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 5"},
    "rsi_long_extra": {"value": 55.0, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 5"},
    "rsi_short_extra": {"value": 45.0, "status": "PENDING", "source": "tv/strategy_a_report.md §2 Gate 5"},
    "ema_fast": {"value": 9, "status": "PENDING", "source": "EMA 9 (report indicators table)"},
    "ema_slow": {"value": 21, "status": "PENDING", "source": "EMA 21 (report indicators table)"},
    "max_risk_points": {"value": None, "status": "PENDING", "source": "Gate 6 — no silent default"},
}

# --- Strategy B: seven rules approved; numeric thresholds not approved ---
STRATEGY_B_RULES = [
    {"id": 1, "text": "Identify the range on the 15m chart: upper resistance and lower support."},
    {"id": 2, "text": "Trade only extremes: upper boundary = evaluate shorts; lower boundary = evaluate longs; middle = WAIT."},
    {"id": 3, "text": "Candlestick confirmation: evaluate engulfing patterns at the boundaries; a single wick is not sufficient."},
    {"id": 4, "text": "Three-chart framework: 15m = range context + confirmation; 5m = directional bias + rejection; 1m = entry refinement. Conflict = WAIT."},
    {"id": 5, "text": "Indicators (VWAP, EMA 21, RSI 14) are supporting evidence only; indicators alone never establish a setup."},
    {"id": 6, "text": "Risk before entry: structural invalidation, dollar risk via correct contract specs; if the structural stop exceeds the risk limit, WAIT."},
    {"id": 7, "text": "Exit and journal: define exit conditions before entry; record setup, confirmation, risk, and review. A disciplined WAIT counts as successful rule-following."},
]

STRATEGY_B_PLACEHOLDERS: Dict[str, Dict[str, Any]] = {
    "range_high": {"value": None, "status": "PENDING", "source": "must be supplied; not invented (01_outline.md R1)"},
    "range_low": {"value": None, "status": "PENDING", "source": "must be supplied; not invented (01_outline.md R1)"},
    "engulfing_validity_window_bars": {"value": None, "status": "PENDING", "source": "grubbot/strategy-b/12_founder_decision_matrix.md"},
    "risk_limit_dollars": {"value": None, "status": "PENDING", "source": "grubbot/strategy-b/12_founder_decision_matrix.md"},
}

MNQ_DOLLARS_PER_POINT = 2.0  # CME MNQ spec; also cited in strategy_a_report.md Gate 6


def _flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def strategy_a_approved() -> bool:
    return _flag("STRATEGY_A_PARAMETERS_APPROVED")


def strategy_b_approved() -> bool:
    return _flag("STRATEGY_B_PARAMETERS_APPROVED")


def strategy_a_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    out = {k: v["value"] for k, v in STRATEGY_A_PLACEHOLDERS.items()}
    if overrides:
        out.update(overrides)
    return out


def pending_keys(placeholders: Dict[str, Dict[str, Any]], params: Dict[str, Any]) -> list[str]:
    missing = []
    for key, meta in placeholders.items():
        if meta["status"] == "PENDING" and params.get(key) is None:
            missing.append(key)
    return missing
