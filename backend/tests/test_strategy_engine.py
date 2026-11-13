"""Unit tests for alerts-only Strategy A / B and the Alerts panel evaluator.

No network, no Discord, no broker, no production writes.
"""
from __future__ import annotations

from typing import List

import pytest

import strategy_engine as eng
import strategy_rules as rules


def _bar(t, o, h, l, c, v=100):
    return {"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v}


def _trend(start: float, n: int, step: float, t0: int = 1_700_000_000, vol: int = 200) -> List[dict]:
    bars = []
    price = start
    for i in range(n):
        o = price
        c = price + step
        hi, lo = max(o, c) + 2, min(o, c) - 2
        bars.append(_bar(t0 + i * 60, o, hi, lo, c, vol))
        price = c
    return bars


def test_engine_status_shows_pending_and_no_execution(monkeypatch):
    monkeypatch.delenv("STRATEGY_A_PARAMETERS_APPROVED", raising=False)
    monkeypatch.delenv("STRATEGY_B_PARAMETERS_APPROVED", raising=False)
    st = eng.engine_status()
    assert st["execution"] == "alerts only — no orders are placed"
    assert st["strategy_a"]["confirmation_alerts"] == "disabled_pending_parameters"
    assert st["strategy_b"]["confirmation_alerts"] == "disabled_pending_parameters"
    assert "max_risk_points" in st["strategy_a"]["pending_placeholders"]
    assert "risk_limit_dollars" in st["strategy_b"]["pending_placeholders"]
    assert "legacy_ema_cross_engine" in st


def test_panel_breakout_above_fires():
    alert = {"id": "a1", "symbol": "MNQ", "alert_type": "breakout", "condition": "above", "target_value": 28000}
    out = eng.evaluate_panel_alert(alert, {"price": 28010, "symbol": "MNQ", "data_label": "delayed"})
    assert out["fire"] is True
    assert out["direction"] == "LONG"
    assert out["strategy"] == "Alerts panel (breakout)"
    assert "28010" in out["trigger"]


def test_panel_breakout_not_met_is_wait():
    alert = {"symbol": "MNQ", "alert_type": "breakout", "condition": "above", "target_value": 28000}
    out = eng.evaluate_panel_alert(alert, {"price": 27900, "data_label": "delayed"})
    assert out["fire"] is False
    assert out["state"] == "WAIT"


def test_panel_vwap_cross_above():
    alert = {"symbol": "MNQ", "alert_type": "vwap_cross", "condition": "above", "target_value": 0}
    snap = {"price": 100.5, "vwap": 100.0, "previous_close": 99.5, "data_label": "delayed", "symbol": "MNQ"}
    out = eng.evaluate_panel_alert(alert, snap)
    assert out["fire"] is True
    assert "VWAP" in out["trigger"]


def test_panel_stop_loss_below():
    alert = {"symbol": "MNQ", "alert_type": "stop_loss", "condition": "below", "target_value": 27900}
    out = eng.evaluate_panel_alert(alert, {"price": 27850, "data_label": "paper"})
    assert out["fire"] is True
    assert out["direction"] == "SHORT"
    assert out["data_label"] == "paper"


def test_strategy_a_does_not_invent_center():
    bars = _trend(28000, 80, 1)
    out = eng.evaluate_strategy_a(bars, center=0.0, approved=True, params={"max_risk_points": 50})
    assert out["fire"] is False
    assert "will not invent" in out["trigger"]


def test_strategy_a_g1_miss_is_wait():
    bars = _trend(28000, 80, 0.5)
    out = eng.evaluate_strategy_a(bars, center=27000, approved=True, params={"max_risk_points": 50, "zone_width_points": 15})
    assert out["fire"] is False
    assert out["gates"]["G1_location"] is False


def test_strategy_a_g6_pending_risk_waits_even_if_approved_flag(monkeypatch):
    """max_risk_points has no silent default — WAIT rather than invent."""
    monkeypatch.setenv("STRATEGY_A_PARAMETERS_APPROVED", "true")
    bars = _trend(28000, 40, 1)
    # Place a center at the last close so G1 can intersect; other gates may still fail,
    # but if we get to G6 the pending cap must block fire.
    center = bars[-1]["close"]
    out = eng.evaluate_strategy_a(bars, center=center, approved=True, params={"max_risk_points": None, "zone_width_points": 500})
    assert out["fire"] is False
    if out.get("parameters_pending"):
        assert "max_risk_points" in out["parameters_pending"]


def test_strategy_a_confirmation_disabled_without_approval():
    # Build a dense range around a center with wide placeholders so more gates can pass,
    # then assert fire is still False when approved=False.
    center = 28000.0
    bars = []
    t0 = 1_700_000_000
    # wander outside the zone, then return and close back above center
    for i in range(40):
        # first 20 bars away from zone, last bars back in zone
        if i < 25:
            o = c = 28200
            bars.append(_bar(t0 + i * 60, o, o + 1, o - 1, c, 300))
        else:
            o = 27990
            c = 28005
            bars.append(_bar(t0 + i * 60, o, 28020, 27980, c, 400))
    out = eng.evaluate_strategy_a(
        bars,
        center=center,
        approved=False,
        es_aligned=True,
        params={**{k: v["value"] for k, v in rules.STRATEGY_A_PLACEHOLDERS.items()}, "max_risk_points": 80, "zone_width_points": 30, "no_chase_ema9_max_points": 200, "no_chase_atr_k": 10},
    )
    assert out["fire"] is False
    # Either a gate WAIT or disabled-pending; never a live confirmation without approval.
    assert out["state"] in {"WAIT", "DISABLED_PENDING_PARAMETERS"}


def test_strategy_b_does_not_invent_range():
    bars = _trend(28000, 80, 0)
    out = eng.evaluate_strategy_b(bars, range_high=None, range_low=None, approved=True, risk_limit_dollars=40)
    assert out["fire"] is False
    assert "will not invent a range" in out["trigger"]


def test_strategy_b_middle_is_wait():
    bars = _trend(28050, 80, 0)  # mid of 28000-28100
    out = eng.evaluate_strategy_b(bars, range_high=28100, range_low=28000, approved=True, risk_limit_dollars=40)
    assert out["fire"] is False
    assert "extreme" in out["trigger"].lower() or "WAIT" in out["trigger"] or "middle" in out["trigger"].lower()
    assert out["rules"]["R2"] is False


def test_strategy_b_single_wick_is_not_enough():
    """R3: a rejection wick at the upper bound without an engulfing body is WAIT."""
    t0 = 1_700_000_000
    bars = []
    # mostly mid then a wick-up 15m-worth of 1m bars that touch 28100 but don't engulf
    for i in range(40):
        bars.append(_bar(t0 + i * 60, 28050, 28055, 28045, 28052, 100))
    # last 15 one-minute bars: long upper wick at the high, close still mid
    for i in range(15):
        bars.append(_bar(t0 + (40 + i) * 60, 28090, 28105, 28085, 28092, 100))
    out = eng.evaluate_strategy_b(bars, range_high=28100, range_low=27900, approved=True, risk_limit_dollars=200)
    assert out["fire"] is False
    # Should fail R2 (close not really at extreme with mid 28000) or R3
    assert out["state"] == "WAIT"


def _b_setup_engulfing_at_low():
    """Enough 1m bars to form two 15m candles: first red, second green engulfing, at range low."""
    t0 = 1_700_000_000
    bars = []
    # 60 bars of mild downtrend to seed EMA/VWAP below price after reversal would fail alignment;
    # instead build a long grind at the low then a strong up bar.
    # First 15m (15 bars): open 100, close 90 (bearish)
    for i in range(15):
        # interpolate 100 -> 90
        o = 100 - i * (10 / 15)
        c = 100 - (i + 1) * (10 / 15)
        bars.append(_bar(t0 + i * 60, o, max(o, c) + 0.2, min(o, c) - 0.2, c, 150))
    # Second 15m: open 89, close 101 (bullish body engulfs 100-90), low touches 85 (range_low)
    for i in range(15):
        o = 89
        c = 89 + (i + 1) * (12 / 15)
        lo = 85 if i == 0 else 88
        bars.append(_bar(t0 + (15 + i) * 60, o, max(o, c) + 0.2, lo, c, 200))
    # more 1m bars continuing up slightly so 5m/1m closes can sit above EMA 21 / VWAP
    last = bars[-1]["close"]
    for i in range(40):
        o = last
        c = last + 0.3
        bars.append(_bar(t0 + (30 + i) * 60, o, c + 0.2, o - 0.2, c, 180))
        last = c
    return bars


def test_strategy_b_preview_when_rules_pass_but_not_approved():
    bars = _b_setup_engulfing_at_low()
    out = eng.evaluate_strategy_b(
        bars,
        range_high=120,
        range_low=85,
        risk_limit_dollars=500,
        approved=False,
        exit_conditions="PAPER: exit if close back through 85; journal the WAIT if invalid",
    )
    assert out["fire"] is False
    # If structure didn't fully pass, we still must not fire. If it did, state is disabled.
    assert out["state"] in {"WAIT", "DISABLED_PENDING_PARAMETERS"}
    if out["state"] == "DISABLED_PENDING_PARAMETERS":
        assert out.get("preview") is True


def test_strategy_b_can_fire_only_when_approved_and_params_supplied():
    bars = _b_setup_engulfing_at_low()
    out = eng.evaluate_strategy_b(
        bars,
        range_high=120,
        range_low=85,
        risk_limit_dollars=500,
        approved=True,
        exit_conditions="PAPER: exit if close back through 85",
        snapshot={"symbol": "MNQ", "data_label": "delayed"},
    )
    if out["fire"]:
        assert out["strategy"] == "B Outer Range Extremes"
        assert out["direction"] == "LONG"
        assert out["data_label"] == "delayed"
        assert "15m confirmation / 5m bias / 1m entry" in out["timeframe"]
        assert "EMA 21" in out["trigger"]
        assert "order flow" not in out["trigger"].lower()
    else:
        # Alignment on a short synthetic may still WAIT; that is acceptable — we only
        # require that approval + params never invent a fire when rules fail, and the
        # reason is explicit.
        assert out["state"] == "WAIT"
        assert out["trigger"]


def test_indicators_labeled_ema9_ema21_vwap_not_proxies():
    bars = _trend(100, 50, 0.2)
    closes = [b["close"] for b in bars]
    a = eng.timeframe_alignment(bars, 21, "LONG")
    assert a["label"] == "EMA 21 and VWAP"
    assert "ema21" in a
    assert "vwap" in a
    assert "ema20" not in a
    # series helpers exist under the documented names
    e9 = eng.ema_series(closes, 9)
    e21 = eng.ema_series(closes, 21)
    assert e9[-1] is not None and e21[-1] is not None


def test_bullish_engulfing_requires_body_not_wick():
    prev = _bar(1, 10, 12, 8, 9)   # bearish body 10->9
    wick = _bar(2, 9.2, 13, 8.5, 9.3)  # small body, huge wick — not engulfing
    real = _bar(2, 8.5, 11, 8.4, 10.5)  # bullish body 8.5->10.5 engulfs 9-10
    assert eng.bullish_engulfing(prev, wick) is False
    assert eng.bullish_engulfing(prev, real) is True


def test_seven_rules_are_exactly_seven():
    assert len(rules.STRATEGY_B_RULES) == 7
    assert rules.STRATEGY_B_RULES[1]["text"].startswith("Trade only extremes")


@pytest.mark.parametrize(
    "value,expected",
    [
        ("true", True),
        ("TRUE", True),
        ("True", True),
        (" true ", True),
        ("True ", True),
        ("1", False),
        ("yes", False),
        ("on", False),
        ("Y", False),
        ("approved", False),
        ("", False),
        ("false", False),
        ("0", False),
    ],
)
def test_approval_flag_is_exactly_true(monkeypatch, value, expected):
    monkeypatch.setenv("STRATEGY_A_PARAMETERS_APPROVED", value)
    monkeypatch.setenv("STRATEGY_B_PARAMETERS_APPROVED", value)
    assert rules.strategy_a_approved() is expected
    assert rules.strategy_b_approved() is expected


def test_approval_flag_unset_is_disabled(monkeypatch):
    monkeypatch.delenv("STRATEGY_A_PARAMETERS_APPROVED", raising=False)
    monkeypatch.delenv("STRATEGY_B_PARAMETERS_APPROVED", raising=False)
    assert rules.strategy_a_approved() is False
    assert rules.strategy_b_approved() is False


def test_strategy_a_flag_on_without_params_does_not_fire(monkeypatch):
    monkeypatch.setenv("STRATEGY_A_PARAMETERS_APPROVED", "true")
    bars = _trend(28000, 40, 1)
    out = eng.evaluate_strategy_a(
        bars,
        center=bars[-1]["close"],
        approved=rules.strategy_a_approved(),
        params={"max_risk_points": None, "zone_width_points": 500},
    )
    assert out["fire"] is False
    assert out.get("parameters_pending") or out["state"] in {"WAIT", "DISABLED_PENDING_PARAMETERS"}


def test_strategy_b_flag_on_without_risk_or_range_does_not_fire(monkeypatch):
    monkeypatch.setenv("STRATEGY_B_PARAMETERS_APPROVED", "true")
    bars = _b_setup_engulfing_at_low()
    missing_risk = eng.evaluate_strategy_b(
        bars,
        range_high=120,
        range_low=85,
        risk_limit_dollars=None,
        approved=rules.strategy_b_approved(),
        exit_conditions="PAPER: exit if close back through 85",
    )
    assert missing_risk["fire"] is False
    missing_range = eng.evaluate_strategy_b(
        bars,
        range_high=None,
        range_low=None,
        risk_limit_dollars=500,
        approved=rules.strategy_b_approved(),
        exit_conditions="PAPER: exit if close back through 85",
    )
    assert missing_range["fire"] is False
    assert "will not invent a range" in missing_range["trigger"]
