"""Correction Round 2 — Zelator's test group C: the malformed-data matrix.

Every malformed input must be a validation error (SignalValidationError,
a ValueError subclass; raw ValueError only where the timestamp parser is
the documented source) and must persist NOTHING — the journal stays
empty. Applied to both adapter paths wherever the field exists on that
path: Strategy A (alert price / timestamp / instrument) and Strategy B
(bars / timestamp / instrument).

Two cells of this matrix were genuine holes before correction round 2
(finding F-4, fixed in signal_pipeline._validate_and_normalize):
  - a present instrument identifier other than exactly "MNQ" was
    journaled ("ES"), and "" / None were silently repaired to "MNQ";
  - a Strategy A alert with price=None was journaled as a QUALIFIED
    record carrying no price.
The remaining cells pin behavior the F-2 correction already enforced.

Control tests at the end prove the matrix is not vacuous: valid events
on both paths still record, and an ABSENT instrument still defaults to
"MNQ" (only a present-but-wrong identifier is malformed).
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import signal_contract as sc
import signal_pipeline as sp

T0 = (1_700_000_000 // 900) * 900
_FULL_A_GATES = {f"G{i}": "PASS" for i in range(1, 7)}


def _bar(t, o, h, l, c, v=100):
    return {"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v}


def _long_fixture():
    """Same deterministic shape as test_bot_b._long_fixture (fires LONG)."""
    bars = []
    i = 0

    def add(o, h, l, c, v):
        nonlocal i
        bars.append(_bar(T0 + i * 60, o, h, l, c, v))
        i += 1

    p = 118.0
    for _ in range(45):
        o = p; c = p - 18 / 45; add(o, o + 0.3, c - 0.3, c, 50); p = c
    for k in range(45):
        o = 99.0; c = 99.0 + (0.2 if k % 2 else -0.2)
        add(o, max(o, c) + 0.3, min(o, c) - 0.3, c, 200)
    p = 100.0
    for _ in range(15):
        o = p; c = p - 8 / 15; add(o, o + 0.3, c - 0.3, c, 300); p = c
    p = 91.0
    for k in range(15):
        o = p; c = p + 13 / 15
        add(o, c + 0.3, 85.0 if k == 0 else o - 0.3, c, 400); p = c
    return bars


def _a_event(alert_over=None, **event_over):
    alert = dict(
        direction="LONG", price=26100.0, bar_time=T0 + 3600, candle_closed=True,
        gate_results=dict(_FULL_A_GATES),
        vwap=26080.0, ema9=26095.0, ema21=26085.0, rsi14=58.0, level=26050.0,
    )
    if alert_over:
        alert.update(alert_over)
    ev = dict(
        event_kind="strategy_a", contract="MNQZ6",
        data_provider="TradingView (alert payload)", data_source="tradingview_alert",
        alert=alert,
    )
    ev.update(event_over)
    return ev


def _b_event(bars, **over):
    ev = dict(
        event_kind="strategy_b",
        contract="MNQZ6",
        data_provider="FIXTURE — synthetic bars, no live feed",
        data_source="test_fixture",
        bars_1m=bars,
        range_high=130,
        range_low=85,
        risk_limit_dollars=500,
        exit_conditions="PAPER: exit on close back through the boundary",
        approved=True,
    )
    ev.update(over)
    return ev


def _pipe(tmp_path, now_ts):
    store = sp.SignalStore(str(tmp_path / "signals.db"))
    now = datetime.fromtimestamp(now_ts, tz=timezone.utc) + timedelta(seconds=30)
    return sp.SignalPipeline(store, now_fn=lambda: now), store


def _a_pipe(tmp_path):
    return _pipe(tmp_path, T0 + 3600)


def _b_pipe(tmp_path, bars):
    return _pipe(tmp_path, bars[-1]["time"])


# --- Strategy A: malformed alert prices ------------------------------------

@pytest.mark.parametrize(
    "bad_price",
    [
        None,
        float("nan"),
        float("inf"),
        float("-inf"),
        True,
        "26100",               # numeric string: rejected, never parsed
        "twenty-six thousand",  # spelled-out: rejected
        -100.0,                # negative price
        0,                     # zero price
    ],
    ids=["none", "nan", "pos_inf", "neg_inf", "bool", "numeric_string",
         "spelled_out", "negative", "zero"],
)
def test_matrix_a_malformed_price_rejected(tmp_path, bad_price):
    pipe, store = _a_pipe(tmp_path)
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_a_event({"price": bad_price}))
    assert store.count() == 0
    assert store.rejection_count() == 0


# --- Strategy A: timestamps -------------------------------------------------

def test_matrix_a_missing_timestamp_rejected(tmp_path):
    pipe, store = _a_pipe(tmp_path)
    ev = _a_event({"bar_time": None})
    assert "data_timestamp" not in ev
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(ev)
    assert store.count() == 0


def test_matrix_a_garbage_timestamp_rejected(tmp_path):
    pipe, store = _a_pipe(tmp_path)
    with pytest.raises(ValueError):  # parser-raised; SignalValidationError is a ValueError
        pipe.process_event(_a_event({"bar_time": "not-a-timestamp"}))
    assert store.count() == 0


# --- Instrument identifiers, both paths -------------------------------------

@pytest.mark.parametrize("bad_instrument", ["ES", "", None, 123],
                         ids=["foreign_symbol", "empty_string", "none", "non_string"])
def test_matrix_a_malformed_instrument_rejected(tmp_path, bad_instrument):
    pipe, store = _a_pipe(tmp_path)
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_a_event(instrument=bad_instrument))
    assert store.count() == 0


@pytest.mark.parametrize("bad_instrument", ["ES", "", None],
                         ids=["foreign_symbol", "empty_string", "none"])
def test_matrix_b_malformed_instrument_rejected(tmp_path, bad_instrument):
    bars = _long_fixture()
    pipe, store = _b_pipe(tmp_path, bars)
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_b_event(bars, instrument=bad_instrument))
    assert store.count() == 0


# --- Strategy B: malformed bars and timestamps -------------------------------

@pytest.mark.parametrize(
    "bad_close",
    [float("nan"), True, "104", -5.0, None],
    ids=["nan_close", "bool_close", "string_close", "negative_close", "none_close"],
)
def test_matrix_b_malformed_bar_close_rejected(tmp_path, bad_close):
    bars = _long_fixture()
    bars[-1] = dict(bars[-1], close=bad_close)
    pipe, store = _b_pipe(tmp_path, _long_fixture())
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_b_event(bars))
    assert store.count() == 0
    assert store.rejection_count() == 0


def test_matrix_b_missing_timestamp_rejected(tmp_path):
    pipe, store = _pipe(tmp_path, T0)
    ev = _b_event([])
    assert "data_timestamp" not in ev
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(ev)
    assert store.count() == 0


def test_matrix_b_garbage_timestamp_rejected(tmp_path):
    pipe, store = _pipe(tmp_path, T0)
    with pytest.raises(ValueError):
        pipe.process_event(_b_event([], data_timestamp="garbage"))
    assert store.count() == 0


# --- Controls: the matrix is not vacuous -------------------------------------

def test_matrix_control_valid_a_alert_records_as_mnq(tmp_path):
    pipe, store = _a_pipe(tmp_path)
    out = pipe.process_event(_a_event())  # no instrument key at all
    assert out["status"] == "RECORDED"
    assert out["record"]["instrument"] == "MNQ"  # absent defaults, present must match
    assert store.count() == 1


def test_matrix_control_valid_b_event_records_as_mnq(tmp_path):
    bars = _long_fixture()
    pipe, store = _b_pipe(tmp_path, bars)
    out = pipe.process_event(_b_event(bars))
    assert out["status"] == "RECORDED"
    assert out["record"]["instrument"] == "MNQ"
    assert store.count() == 1
