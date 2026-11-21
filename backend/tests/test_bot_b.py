"""Bot B — Outer Range Extremes detector tests (Master Prompt s.7).

Every case records its expected result in the test name/assertions.
No network, no Discord, no broker, no production writes. Fixtures only —
there is no historical MNQ archive in this repo, and nothing here is
presented as live-market validation.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

import bot_b
import strategy_engine as eng  # noqa: F401  (ensures the engine imports cleanly)

T0 = (1_700_000_000 // 900) * 900  # aligned to a 15m bucket boundary
EXITS = "PAPER: exit on close back through the boundary"
NOW = datetime(2026, 11, 15, 15, 0, tzinfo=timezone.utc)


def _bar(t, o, h, l, c, v=100):
    return {"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v}


def _long_fixture():
    """Decline, flat grind, bearish 15m, then a bullish-engulfing 15m whose
    low touches range_low=85. Deterministically fires in the evaluator when
    approved + parameters are supplied (all Seven Rules pass; $38 risk)."""
    bars = []
    i = 0

    def add(o, h, l, c, v):
        nonlocal i
        bars.append(_bar(T0 + i * 60, o, h, l, c, v))
        i += 1

    p = 118.0
    for _ in range(45):  # decline 118 -> 100
        o = p; c = p - 18 / 45; add(o, o + 0.3, c - 0.3, c, 50); p = c
    for k in range(45):  # flat grind ~99
        o = 99.0; c = 99.0 + (0.2 if k % 2 else -0.2)
        add(o, max(o, c) + 0.3, min(o, c) - 0.3, c, 200)
    p = 100.0
    for _ in range(15):  # prev 15m: bearish 100 -> 92
        o = p; c = p - 8 / 15; add(o, o + 0.3, c - 0.3, c, 300); p = c
    p = 91.0
    for k in range(15):  # cur 15m: bullish engulfing 91 -> 104, low touches 85
        o = p; c = p + 13 / 15
        add(o, c + 0.3, 85.0 if k == 0 else o - 0.3, c, 400); p = c
    return bars


def _mirror(bars, axis=215.0):
    """Mirror a fixture around a price axis (LONG setup -> SHORT setup)."""
    return [
        _bar(b["time"], axis - b["open"], axis - b["low"], axis - b["high"], axis - b["close"], b["volume"])
        for b in bars
    ]


def _flat_fixture(price=107.0, n=40):
    return [_bar(T0 + i * 60, price, price + 0.4, price - 0.4, price, 100) for i in range(n)]


def _kwargs(**over):
    kw = dict(range_high=130, range_low=85, risk_limit_dollars=500,
              exit_conditions=EXITS, approved=True)
    kw.update(over)
    return kw


# --- Prompt case: price reaching the lower boundary (valid engulfing) ---

def test_lower_boundary_valid_engulfing_is_validated_paper_signal():
    rec = bot_b.evaluate_bot_b(_long_fixture(), **_kwargs())
    assert rec["classification"] == "VALIDATED PAPER SIGNAL"
    assert rec["direction"] == "LONG"
    assert rec["paper_trade"] is not None
    assert rec["paper_trade"]["action"] == "BUY"
    assert rec["paper_trade"]["data_label"] == "PAPER"
    assert rec["paper_trade"]["dollar_risk_per_contract"] == pytest.approx(38.0)


# --- Prompt case: price reaching the upper boundary ---

def test_upper_boundary_valid_engulfing_is_validated_short():
    rec = bot_b.evaluate_bot_b(_mirror(_long_fixture()), **_kwargs())
    assert rec["classification"] == "VALIDATED PAPER SIGNAL"
    assert rec["direction"] == "SHORT"
    assert rec["paper_trade"]["action"] == "SELL"


# --- Prompt case: price remaining in the middle ---

def test_middle_is_waiting():
    rec = bot_b.evaluate_bot_b(_flat_fixture(), **_kwargs())
    assert rec["classification"] == "WAITING"
    assert rec["paper_trade"] is None


def test_approaching_lower_boundary_is_potential_setup():
    bars = []
    p = 100.0
    for i in range(30):  # descend 100 -> 94, never touching 85
        o = p; c = p - 0.2
        bars.append(_bar(T0 + i * 60, o, o + 0.3, c - 0.3, c, 100)); p = c
    rec = bot_b.evaluate_bot_b(bars, **_kwargs())
    assert rec["classification"] == "POTENTIAL SETUP"
    assert rec["direction"] == "LONG"


# --- Prompt case: false engulfing pattern ---

def test_false_engulfing_wick_only_is_confirmation_pending():
    bars = _long_fixture()[:105]  # through the bearish prev 15m
    p = 95.0
    for k in range(15):  # wick touches 85, body small and non-engulfing
        o = p; c = 95.5 if k % 2 else 94.8
        bars.append(_bar(T0 + (105 + k) * 60, o, max(o, c) + 0.3, 85.0 if k == 0 else min(o, c) - 0.3, c, 300))
        p = c
    rec = bot_b.evaluate_bot_b(bars, **_kwargs())
    assert rec["classification"] == "CONFIRMATION PENDING"
    assert rec["paper_trade"] is None
    assert any(label.startswith("R3") for label in rec["conditions_failed"])


# --- Prompt cases: VWAP / EMA conflicts (evaluator Rule 4 alignment) ---

def test_indicator_conflict_is_no_trade():
    heavy_top = [_bar(T0 - (30 - i) * 60, 125.0, 125.3, 124.7, 125.0, 2000) for i in range(30)]
    rec = bot_b.evaluate_bot_b(heavy_top + _long_fixture(), **_kwargs())
    assert rec["classification"] == "NO TRADE"
    assert any(label.startswith("R4") for label in rec["conditions_failed"])


# --- Prompt case: incomplete entry confirmation ---

def test_incomplete_confirmation_bar_is_confirmation_pending():
    bars = _long_fixture()[:110]  # engulfing 15m bar only 5 minutes old
    rec = bot_b.evaluate_bot_b(bars, **_kwargs())
    assert rec["classification"] == "CONFIRMATION PENDING"
    assert rec["paper_trade"] is None


# --- Prompt cases: missing and delayed market data ---

def test_missing_data_is_waiting_never_a_signal():
    assert bot_b.evaluate_bot_b([], **_kwargs())["classification"] == "WAITING"
    assert bot_b.evaluate_bot_b(None, **_kwargs())["classification"] == "WAITING"


def test_malformed_data_is_no_trade():
    bad = [{"time": 1, "open": "x", "high": 2, "low": 0.5, "close": 1}]
    assert bot_b.evaluate_bot_b(bad, **_kwargs())["classification"] == "NO TRADE"
    inverted = [_bar(T0, 100, 90, 110, 100)]  # high below low
    assert bot_b.evaluate_bot_b(inverted, **_kwargs())["classification"] == "NO TRADE"


def test_stale_snapshot_is_rejected():
    snap = {"symbol": "MNQ", "data_label": "delayed", "fetched_at": 1_600_000_000}
    rec = bot_b.evaluate_bot_b(_long_fixture(), snapshot=snap, now=NOW, **_kwargs())
    assert rec["classification"] == "NO TRADE"
    assert "stale" in rec["explanation"]


def test_snapshot_without_timestamp_fails_closed():
    snap = {"symbol": "MNQ", "data_label": "delayed"}
    rec = bot_b.evaluate_bot_b(_long_fixture(), snapshot=snap, now=NOW, **_kwargs())
    assert rec["classification"] == "NO TRADE"


def test_fresh_snapshot_passes_the_data_gate():
    snap = {"symbol": "MNQ", "data_label": "delayed", "fetched_at": NOW.timestamp() - 60}
    rec = bot_b.evaluate_bot_b(_long_fixture(), snapshot=snap, now=NOW, **_kwargs())
    assert rec["classification"] == "VALIDATED PAPER SIGNAL"


# --- Safety gates: approval and parameters ---

def test_unapproved_rules_pass_is_never_validated():
    rec = bot_b.evaluate_bot_b(_long_fixture(), **_kwargs(approved=False))
    assert rec["classification"] == "CONFIRMATION PENDING"
    assert rec["paper_trade"] is None


def test_missing_range_is_waiting_and_invents_nothing():
    rec = bot_b.evaluate_bot_b(_long_fixture(), **_kwargs(range_high=None, range_low=None))
    assert rec["classification"] == "WAITING"
    assert "range_high" in rec["parameters_pending"]


def test_invalid_range_is_no_trade():
    rec = bot_b.evaluate_bot_b(_long_fixture(), **_kwargs(range_high=80, range_low=90))
    assert rec["classification"] == "NO TRADE"


def test_missing_risk_limit_is_confirmation_pending():
    rec = bot_b.evaluate_bot_b(_long_fixture(), **_kwargs(risk_limit_dollars=None))
    assert rec["classification"] == "CONFIRMATION PENDING"
    assert "risk_limit_dollars" in rec["parameters_pending"]


def test_stop_over_risk_limit_is_no_trade():
    rec = bot_b.evaluate_bot_b(_long_fixture(), **_kwargs(risk_limit_dollars=10))
    assert rec["classification"] == "NO TRADE"


def test_missing_exit_conditions_is_confirmation_pending():
    rec = bot_b.evaluate_bot_b(_long_fixture(), **_kwargs(exit_conditions=None))
    assert rec["classification"] == "CONFIRMATION PENDING"
    assert rec["paper_trade"] is None


# --- Prompt s.4: the explanation record is complete ---

def test_explanation_record_has_every_prompt_field():
    rec = bot_b.evaluate_bot_b(_long_fixture(), **_kwargs())
    for field in ("instrument", "strategy", "timestamp", "timezone", "range", "price",
                  "confirmation_5m", "entry_1m", "ema", "vwap", "volume",
                  "conditions_passed", "conditions_failed", "classification", "explanation"):
        assert field in rec, field
    assert rec["instrument"] == "MNQ"
    assert rec["strategy"] == "Outer Range Extremes"
    assert rec["timezone"] == "America/New_York"
    assert rec["range"] == {"high": 130, "low": 85}
    assert rec["explanation"]


# --- Prompt case: duplicate signals ---

def test_duplicate_evaluations_are_suppressed_in_the_audit_trail():
    det = bot_b.BotBDetector()
    first = det.evaluate(_long_fixture(), **_kwargs())
    second = det.evaluate(_long_fixture(), **_kwargs())
    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert len(det.records) == 1
    third = det.evaluate(_flat_fixture(), **_kwargs())
    assert third["duplicate"] is False
    assert len(det.records) == 2
