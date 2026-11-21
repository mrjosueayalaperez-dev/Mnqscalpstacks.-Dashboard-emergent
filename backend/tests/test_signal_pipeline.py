"""Structured Signal Contract + Pipeline tests (Phase 2, Tasks 3+4+5).

Fixtures only — synthetic bars mirrored from test_bot_b.py's proven shapes.
No network, no Mongo, no production writes: the store is a temp SQLite file.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import signal_contract as sc
import signal_pipeline as sp

T0 = (1_700_000_000 // 900) * 900  # aligned to a 15m bucket boundary
EXITS = "PAPER: exit on close back through the boundary"


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


def _mirror(bars, axis=215.0):
    return [
        _bar(b["time"], axis - b["open"], axis - b["low"], axis - b["high"], axis - b["close"], b["volume"])
        for b in bars
    ]


def _flat_fixture(price=107.0, n=40):
    return [_bar(T0 + i * 60, price, price + 0.4, price - 0.4, price, 100) for i in range(n)]


def _last_bar_dt(bars):
    return datetime.fromtimestamp(bars[-1]["time"], tz=timezone.utc)


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
        exit_conditions=EXITS,
        approved=True,
    )
    ev.update(over)
    return ev


def _pipeline(tmp_path, bars, *, age_seconds=30, **kw):
    store = sp.SignalStore(str(tmp_path / "signals.db"))
    now = _last_bar_dt(bars) + timedelta(seconds=age_seconds)
    return sp.SignalPipeline(store, now_fn=lambda: now, **kw), store


def _all_keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            keys.add(k)
            keys |= _all_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            keys |= _all_keys(v)
    return keys


# --- Strategy B: qualified records -----------------------------------------

def test_valid_b_long_qualified_record_full_provenance(tmp_path):
    bars = _long_fixture()
    pipe, store = _pipeline(tmp_path, bars)
    out = pipe.process_event(_b_event(bars))
    assert out["status"] == "RECORDED" and out["created"] is True
    assert out["order_created"] is False
    rec = out["record"]
    assert rec["classification"]["classification"] == "LONG"
    assert rec["classification"]["qualification_status"] == "qualified"
    assert rec["classification"]["gate_results"] == {f"R{i}": "PASS" for i in range(1, 8)}
    # The 6 strict mapping gaps, filled from pipeline context:
    assert rec["schema_version"] == "1.0"
    assert rec["contract"] == "MNQZ6"
    assert rec["data_provider"].startswith("FIXTURE")
    assert rec["session"] in ("RTH", "ETH")
    assert rec["strategy_id"] == "STRATEGY_B"
    assert rec["strategy_version"] == "MQU-SB-001 v1.0"
    assert rec["risk"]["risk_config_version"] == "UNAPPROVED-v0"
    # Market state carried from the detector:
    assert rec["market_state"]["price"] == pytest.approx(104.0)
    assert rec["market_state"]["range_low"] == 85
    assert rec["market_state"]["vwap"]["relationship"] is not None
    # Risk is analytical only — reference entry + structural stop, no order fields:
    assert rec["risk"]["proposed_entry"] == pytest.approx(104.0)
    assert rec["risk"]["structural_stop"] is not None
    assert rec["risk"]["stop_distance_points"] == pytest.approx(19.0)
    assert rec["risk"]["quantity"] is None and rec["risk"]["target"] is None
    assert rec["risk"]["risk_approval_status"] == "UNAPPROVED"
    assert rec["ai_explanation"]["explanation_source"] == sc.EXPLANATION_SOURCE_FALLBACK
    assert store.count() == 1


def test_valid_b_short_qualified_record(tmp_path):
    bars = _mirror(_long_fixture())
    pipe, _ = _pipeline(tmp_path, bars)
    out = pipe.process_event(_b_event(bars))
    rec = out["record"]
    assert rec["classification"]["classification"] == "SHORT"
    assert rec["classification"]["qualification_status"] == "qualified"
    assert rec["risk"]["quantity"] is None


# --- Strategy B: rejections --------------------------------------------------

def test_b_mid_range_is_no_trade_with_reason(tmp_path):
    bars = _flat_fixture()
    pipe, store = _pipeline(tmp_path, bars)
    out = pipe.process_event(_b_event(bars))
    rec = out["record"]
    assert rec["classification"]["classification"] == "NO_TRADE"
    assert rec["classification"]["qualification_status"] == "awaiting_data_or_range"
    assert any("mid-range" in r for r in rec["classification"]["rejection_reasons"])
    assert store.count() == 1  # rejections are journaled too


def test_open_candle_rejected_before_evaluation(tmp_path):
    bars = _long_fixture()
    pipe, _ = _pipeline(tmp_path, bars)
    out = pipe.process_event(_b_event(bars, candle_closed=False))
    rec = out["record"]
    assert rec["classification"]["classification"] == "NO_TRADE"
    assert rec["classification"]["rejection_status"] == "OPEN_CANDLE"
    assert rec["classification"]["gate_results"] == {"CANDLE_CLOSED": "FAIL"}


def test_stale_data_rejected_with_stale_reason(tmp_path):
    bars = _long_fixture()
    pipe, store = _pipeline(tmp_path, bars, age_seconds=10_000)
    out = pipe.process_event(_b_event(bars))
    rec = out["record"]
    assert rec["classification"]["classification"] == "NO_TRADE"
    assert rec["classification"]["rejection_status"] == "STALE_DATA"
    assert rec["classification"]["stale_data_reasons"], "stale reason must be recorded"
    assert rec["market_state"]["data_freshness"] == "STALE"
    assert store.count() == 1


# --- Envelope / contract validation -------------------------------------------

def test_missing_required_field_is_validation_error(tmp_path):
    bars = _long_fixture()
    pipe, store = _pipeline(tmp_path, bars)
    ev = _b_event(bars)
    del ev["contract"]
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(ev)
    assert store.count() == 0


def test_invented_risk_rejected_by_contract():
    rec = sc.new_signal_record(
        strategy_id="STRATEGY_B", strategy_version=sc.STRATEGY_B_VERSION,
        instrument="MNQ", contract="MNQZ6", data_provider="FIXTURE",
        data_source="test", data_timestamp="2026-11-20T14:30:00+00:00",
        received_timestamp="2026-11-20T14:30:30+00:00", session="RTH",
        timeframe="1m", candle_timestamp="2026-11-20T14:30:00+00:00",
    )
    rec["risk"]["quantity"] = 1  # smuggled order field under UNAPPROVED risk
    with pytest.raises(sc.SignalValidationError):
        sc.validate_signal_record(rec)


# --- Idempotency ----------------------------------------------------------------

def test_duplicate_event_returns_existing_and_creates_nothing(tmp_path):
    bars = _long_fixture()
    pipe, store = _pipeline(tmp_path, bars)
    ev = _b_event(bars)
    first = pipe.process_event(ev)
    second = pipe.process_event(ev)
    assert second["status"] == "DUPLICATE"
    assert second["created"] is False
    assert second["record"]["signal_id"] == first["record"]["signal_id"]
    assert store.count() == 1


# --- Fail-closed persistence ------------------------------------------------------

class _FailingStore:
    def get_by_idempotency_key(self, key):
        return None

    def put(self, rec):
        raise sp.PersistenceError("injected store failure")

    def count(self):
        return 0


def test_persistence_failure_fails_closed():
    bars = _long_fixture()
    now = _last_bar_dt(bars) + timedelta(seconds=30)
    pipe = sp.SignalPipeline(_FailingStore(), now_fn=lambda: now)
    with pytest.raises(sp.PipelinePersistenceError) as excinfo:
        pipe.process_event(_b_event(bars))
    assert excinfo.value.record["persistence_status"] == "PERSISTENCE_FAILED"


# --- Paper-order firewall -----------------------------------------------------------

def test_unapproved_risk_creates_no_order_anywhere(tmp_path):
    bars = _long_fixture()
    pipe, _ = _pipeline(tmp_path, bars)
    out = pipe.process_event(_b_event(bars))
    assert out["order_created"] is False
    keys = _all_keys(out["record"])
    order_like = [k for k in keys if re.search(r"(^|_)(order|fill|position)(s|_id)?($|_)", k)]
    assert not order_like, f"order-shaped keys present in a signal record: {order_like}"
    assert out["record"]["risk"]["quantity"] is None
    assert out["record"]["risk"]["max_simulated_exposure"] is None


# --- Strategy A adapter -------------------------------------------------------------

def _a_event(**alert_over):
    alert = dict(
        direction="LONG", price=26100.0, bar_time=T0 + 3600, candle_closed=True,
        gate_results={"G1": "PASS", "G2": "PASS"},  # G3–G6 not supplied
        vwap=26080.0, ema9=26095.0, ema21=26085.0, rsi14=58.0, level=26050.0,
    )
    alert.update(alert_over)
    return dict(
        event_kind="strategy_a", contract="MNQZ6",
        data_provider="TradingView (alert payload)", data_source="tradingview_alert",
        alert=alert,
    )


def _a_pipeline(tmp_path):
    store = sp.SignalStore(str(tmp_path / "signals.db"))
    now = datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) + timedelta(seconds=30)
    return sp.SignalPipeline(store, now_fn=lambda: now), store


def test_strategy_a_unverifiable_gates_marked_not_evaluable(tmp_path):
    pipe, _ = _a_pipeline(tmp_path)
    out = pipe.process_event(_a_event())
    rec = out["record"]
    assert rec["strategy_id"] == "STRATEGY_A"
    gates = rec["classification"]["gate_results"]
    assert gates["G1"] == "PASS" and gates["G2"] == "PASS"
    assert gates["G3"] == gates["G4"] == gates["G5"] == gates["G6"] == "NOT_EVALUABLE"
    assert rec["classification"]["classification"] == "NO_TRADE"
    assert rec["classification"]["rejection_status"] == "GATE_NOT_EVALUABLE"


def test_strategy_a_full_pass_alert_is_qualified_as_reported(tmp_path):
    pipe, _ = _a_pipeline(tmp_path)
    full = {f"G{i}": "PASS" for i in range(1, 7)}
    out = pipe.process_event(_a_event(gate_results=full))
    rec = out["record"]
    assert rec["classification"]["classification"] == "LONG"
    assert rec["classification"]["qualification_status"] == "qualified_alert_reported"
    assert rec["risk"]["quantity"] is None  # still never an order


def test_strategy_a_record_cannot_be_relabeled_b():
    pipe_store = sp.SignalStore(":memory:")
    now = datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) + timedelta(seconds=30)
    pipe = sp.SignalPipeline(pipe_store, now_fn=lambda: now)
    rec = pipe.process_event(_a_event())["record"]
    relabeled = dict(rec, strategy_id="STRATEGY_B")
    with pytest.raises(sc.SignalValidationError):
        sc.validate_signal_record(relabeled, expected_strategy_id="STRATEGY_A")
    with pytest.raises(sc.SignalValidationError):
        sc.validate_signal_record(relabeled)  # idempotency key embeds STRATEGY_A


# --- Finding F-2: numeric sanity (battery scenario 15) --------------------
#
# Before the fix, the Strategy A adapter recorded an alert price of
# -100.0 — and even the string "twenty-six thousand" — as a QUALIFIED
# LONG signal, because validate_signal_record checked provenance and
# risk fields but never market-state numerics. These tests pin the
# corrected behavior: malformed numbers are validation errors and
# persist NOTHING, on both adapter paths.

_FULL_A_GATES = {f"G{i}": "PASS" for i in range(1, 7)}


def test_f2_strategy_a_negative_price_is_validation_error(tmp_path):
    pipe, store = _a_pipeline(tmp_path)
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_a_event(price=-100.0, gate_results=dict(_FULL_A_GATES)))
    assert store.count() == 0


def test_f2_strategy_a_string_price_is_validation_error(tmp_path):
    pipe, store = _a_pipeline(tmp_path)
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(
            _a_event(price="twenty-six thousand", gate_results=dict(_FULL_A_GATES))
        )
    assert store.count() == 0


def test_f2_strategy_a_bool_price_is_validation_error(tmp_path):
    # bool is an int subclass; it must not smuggle through as a number.
    pipe, store = _a_pipeline(tmp_path)
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_a_event(price=True, gate_results=dict(_FULL_A_GATES)))
    assert store.count() == 0


def test_f2_strategy_b_string_close_bar_is_validation_error(tmp_path):
    bars = _long_fixture()
    bars[-1] = dict(bars[-1], close="one hundred four")
    pipe, store = _pipeline(tmp_path, _long_fixture())
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_b_event(bars))
    assert store.count() == 0


def test_f2_strategy_b_negative_close_bar_is_validation_error(tmp_path):
    bars = _long_fixture()
    bars[-1] = dict(bars[-1], close=-5.0, low=-6.0)
    pipe, store = _pipeline(tmp_path, _long_fixture())
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_b_event(bars))
    assert store.count() == 0


def test_f2_contract_numeric_sanity_direct():
    """Contract level: a valid numeric record validates; textual,
    boolean, NaN, and non-positive-price variants are rejected."""
    rec = sc.new_signal_record(
        strategy_id="STRATEGY_B", strategy_version=sc.STRATEGY_B_VERSION,
        instrument="MNQ", contract="MNQZ6", data_provider="FIXTURE",
        data_source="test", data_timestamp="2026-11-20T14:30:00+00:00",
        received_timestamp="2026-11-20T14:30:30+00:00", session="RTH",
        timeframe="1m", candle_timestamp="2026-11-20T14:30:00+00:00",
        market_state={
            "price": 26100.0,
            "vwap": {"value": 26080.0, "relationship": "price above VWAP"},
            "ema9": 26095.0, "ema21": 26085.0, "rsi14": 58.0,
            "range_high": 26200, "range_low": 26000,
        },
    )
    assert sc.validate_signal_record(rec) is rec  # valid record still validates
    for field, bad in (("price", "twenty-six thousand"), ("price", True),
                       ("price", -1.0), ("price", float("nan")),
                       ("rsi14", "high"), ("ema9", "26095")):
        broken = json.loads(sc.to_json(rec))
        broken["market_state"][field] = bad
        with pytest.raises(sc.SignalValidationError):
            sc.validate_signal_record(broken)


# --- Finding F-1: out-of-order guard (battery scenario 13) -----------------
#
# Before the fix, an older-but-fresh event was silently journaled as a
# second current record. Now it is preserved as a NO_TRADE /
# OUT_OF_ORDER rejection in the store's audit table and returned as
# REJECTED; the journal (and any "latest" read of it) is untouched.

def test_f1_out_of_order_event_rejected_to_audit_not_journal(tmp_path):
    bars_new = _long_fixture()
    pipe, store = _pipeline(tmp_path, bars_new)
    first = pipe.process_event(_b_event(bars_new))
    assert first["status"] == "RECORDED"

    bars_old = _flat_fixture()  # every candle older than bars_new's last
    ev_old = _b_event(
        bars_old,
        received_at=(_last_bar_dt(bars_old) + timedelta(seconds=30)).isoformat(),
    )
    second = pipe.process_event(ev_old)
    assert second["status"] == "REJECTED"
    assert second["created"] is False
    assert second["order_created"] is False
    assert second["audit_recorded"] is True
    # Journal unchanged: still exactly the one qualified record.
    assert store.count() == 1
    # The rejection exists — in the audit trail, as a NO_TRADE record.
    assert store.rejection_count() == 1
    rej = store.get_rejections()[0]
    assert rej["classification"]["classification"] == "NO_TRADE"
    assert rej["classification"]["rejection_status"] == "OUT_OF_ORDER"
    assert rej["signal_id"] == second["record"]["signal_id"]
    # A "latest qualified" read is unaffected by the out-of-order event.
    latest = store.get_by_idempotency_key(first["record"]["idempotency_key"])
    assert latest["signal_id"] == first["record"]["signal_id"]
    assert latest["classification"]["qualification_status"] == "qualified"


def test_f1_watermark_survives_store_restart(tmp_path):
    path = str(tmp_path / "signals.db")
    bars_new = _long_fixture()
    store = sp.SignalStore(path)
    now = _last_bar_dt(bars_new) + timedelta(seconds=30)
    sp.SignalPipeline(store, now_fn=lambda: now).process_event(_b_event(bars_new))
    store.close()

    store2 = sp.SignalStore(path)  # reopened: watermark derives from the journal
    bars_old = _flat_fixture()
    pipe2 = sp.SignalPipeline(
        store2, now_fn=lambda: _last_bar_dt(bars_old) + timedelta(seconds=30)
    )
    out = pipe2.process_event(
        _b_event(
            bars_old,
            received_at=(_last_bar_dt(bars_old) + timedelta(seconds=30)).isoformat(),
        )
    )
    assert out["status"] == "REJECTED"
    assert store2.count() == 1
    assert store2.rejection_count() == 1
    store2.close()


def test_f1_equal_timestamp_event_is_not_out_of_order(tmp_path):
    bars = _long_fixture()
    pipe, store = _pipeline(tmp_path, bars)
    first = pipe.process_event(_b_event(bars))
    assert first["status"] == "RECORDED"
    # Same signal candle, different source event: idempotency does not
    # claim it, and the ordering guard must not reject an EQUAL time.
    second = pipe.process_event(_b_event(bars, source_event_id="evt-second"))
    assert second["status"] == "RECORDED"
    assert store.count() == 2
    assert store.rejection_count() == 0
