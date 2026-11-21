"""Correction Round 2 — Zelator's additional test groups A and B, plus
the F-1 watermark-key refinement regressions.

Group A — Replay / idempotency / out-of-order delivery: the same signal
delivered repeatedly must journal exactly once; an older signal must
land in the audit trail, never the journal; a newer signal must advance
the "latest qualified" read, which must never regress.

Group B — Strategy A/B field isolation: a Strategy A record must carry
no Strategy B artifacts (and vice versa), and sharing one store must
not contaminate either record.

F-1 refinement — the ordering watermark key is (strategy, instrument,
TIMEFRAME) per Zelator's correction-round specification: ordering is
enforced independently per timeframe and per strategy.

Fixtures only — synthetic bars mirrored from test_signal_pipeline.py's
proven shapes. No network, no Mongo, no production writes.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import signal_contract as sc
import signal_pipeline as sp

T0 = (1_700_000_000 // 900) * 900  # aligned to a 15m bucket boundary
EXITS = "PAPER: exit on close back through the boundary"
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


def _flat_fixture(price=107.0, n=40):
    return [_bar(T0 + i * 60, price, price + 0.4, price - 0.4, price, 100) for i in range(n)]


def _shift(bars, seconds):
    return [dict(b, time=b["time"] + seconds) for b in bars]


def _last_bar_dt(bars):
    return datetime.fromtimestamp(bars[-1]["time"], tz=timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


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


def _a_event(alert_over=None, **event_over):
    alert = dict(
        direction="LONG", price=26100.0, bar_time=T0 + 3600, candle_closed=True,
        gate_results=dict(_FULL_A_GATES),
        vwap=26080.0, ema9=26095.0, ema21=26085.0, rsi14=58.0,
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


def _pipeline(tmp_path, now):
    store = sp.SignalStore(str(tmp_path / "signals.db"))
    return sp.SignalPipeline(store, now_fn=lambda: now), store


# --- Group A: replay / idempotency / out-of-order delivery -----------------

def test_group_a_replay_same_b_event_three_times_journals_once(tmp_path):
    bars = _long_fixture()
    pipe, store = _pipeline(tmp_path, _last_bar_dt(bars) + timedelta(seconds=30))
    ev = _b_event(bars)
    first = pipe.process_event(ev)
    second = pipe.process_event(ev)
    third = pipe.process_event(ev)
    assert first["status"] == "RECORDED" and first["created"] is True
    assert second["status"] == "DUPLICATE" and second["created"] is False
    assert third["status"] == "DUPLICATE" and third["created"] is False
    sid = first["record"]["signal_id"]
    assert second["record"]["signal_id"] == sid
    assert third["record"]["signal_id"] == sid
    assert store.count() == 1  # exactly one journal entry after 3 deliveries
    assert store.rejection_count() == 0
    assert first["order_created"] is second["order_created"] is third["order_created"] is False


def test_group_a_replay_out_of_order_then_newer_latest_never_regresses(tmp_path):
    bars_new = _long_fixture()
    pipe, store = _pipeline(tmp_path, _last_bar_dt(bars_new) + timedelta(seconds=30))

    first = pipe.process_event(_b_event(bars_new))
    assert first["status"] == "RECORDED"
    sid_first = first["record"]["signal_id"]
    # A replay of the same delivery changes nothing.
    assert pipe.process_event(_b_event(bars_new))["status"] == "DUPLICATE"
    assert store.count() == 1
    latest = store.latest_qualified("STRATEGY_B", "MNQ", "1m")
    assert latest is not None and latest["signal_id"] == sid_first

    # An older event arriving late: audit trail, never the journal, and
    # the latest-qualified read does not regress.
    bars_old = _flat_fixture()
    out_old = pipe.process_event(
        _b_event(bars_old, received_at=_iso(_last_bar_dt(bars_old) + timedelta(seconds=30)))
    )
    assert out_old["status"] == "REJECTED"
    assert out_old["record"]["classification"]["rejection_status"] == "OUT_OF_ORDER"
    assert store.count() == 1
    assert store.rejection_count() == 1
    latest = store.latest_qualified("STRATEGY_B", "MNQ", "1m")
    assert latest["signal_id"] == sid_first

    # A newer event advances the state — to the newer record, only.
    bars_newer = _shift(_long_fixture(), 7200)  # +2h, still 15m-aligned
    out_newer = pipe.process_event(
        _b_event(bars_newer, received_at=_iso(_last_bar_dt(bars_newer) + timedelta(seconds=30)))
    )
    assert out_newer["status"] == "RECORDED"
    assert out_newer["record"]["classification"]["qualification_status"] == "qualified"
    sid_newer = out_newer["record"]["signal_id"]
    assert sid_newer != sid_first
    assert store.count() == 2
    latest = store.latest_qualified("STRATEGY_B", "MNQ", "1m")
    assert latest["signal_id"] == sid_newer
    assert latest["market_state"]["candle_timestamp"] > first["record"]["market_state"]["candle_timestamp"]


def test_group_a_replay_same_a_alert_twice_journals_once(tmp_path):
    now = datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) + timedelta(seconds=30)
    pipe, store = _pipeline(tmp_path, now)
    ev = _a_event()
    first = pipe.process_event(ev)
    second = pipe.process_event(ev)
    assert first["status"] == "RECORDED"
    assert second["status"] == "DUPLICATE" and second["created"] is False
    assert second["record"]["signal_id"] == first["record"]["signal_id"]
    assert store.count() == 1
    assert store.rejection_count() == 0


# --- F-1 refinement: watermark key is (strategy, instrument, timeframe) ---

def test_f1r_watermark_enforced_independently_per_timeframe(tmp_path):
    pipe, store = _pipeline(tmp_path, datetime.fromtimestamp(T0, tz=timezone.utc))

    def a_at(bar_ts, timeframe):
        return _a_event(
            {"bar_time": bar_ts, "timeframe": timeframe},
            received_at=_iso(datetime.fromtimestamp(bar_ts, tz=timezone.utc) + timedelta(seconds=30)),
        )

    # A newer 5m record is journaled first.
    out_5m = pipe.process_event(a_at(T0 + 3600, "5m"))
    assert out_5m["status"] == "RECORDED"
    assert out_5m["record"]["timeframe"] == "5m"
    # An OLDER 1m event is not blocked by the 5m watermark: the 1m key
    # has no watermark yet, so it journals as the first 1m record.
    out_1m = pipe.process_event(a_at(T0 + 1800, "1m"))
    assert out_1m["status"] == "RECORDED"
    assert out_1m["record"]["timeframe"] == "1m"
    # Each timeframe's watermark is exactly its own newest candle.
    assert store.watermark("STRATEGY_A", "MNQ", "5m") == _iso(
        datetime.fromtimestamp(T0 + 3600, tz=timezone.utc))
    assert store.watermark("STRATEGY_A", "MNQ", "1m") == _iso(
        datetime.fromtimestamp(T0 + 1800, tz=timezone.utc))
    # Below its OWN timeframe's watermark, each is out of order — the
    # 5m rejection is older than the 1m watermark too, proving the 1m
    # key neither blocks nor excuses it; its own 5m key decides.
    out_1m_old = pipe.process_event(a_at(T0 + 900, "1m"))
    assert out_1m_old["status"] == "REJECTED"
    assert out_1m_old["record"]["classification"]["rejection_status"] == "OUT_OF_ORDER"
    assert out_1m_old["record"]["timeframe"] == "1m"
    out_5m_old = pipe.process_event(a_at(T0 + 2700, "5m"))
    assert out_5m_old["status"] == "REJECTED"
    assert out_5m_old["record"]["classification"]["rejection_status"] == "OUT_OF_ORDER"
    assert out_5m_old["record"]["timeframe"] == "5m"
    assert store.count() == 2
    assert store.rejection_count() == 2
    # Latest-qualified reads are per-timeframe as well.
    assert store.latest_qualified("STRATEGY_A", "MNQ", "5m")["signal_id"] == out_5m["record"]["signal_id"]
    assert store.latest_qualified("STRATEGY_A", "MNQ", "1m")["signal_id"] == out_1m["record"]["signal_id"]


def test_f1r_watermark_enforced_independently_per_strategy(tmp_path):
    bars = _long_fixture()
    pipe, store = _pipeline(tmp_path, _last_bar_dt(bars) + timedelta(seconds=30))
    out_b = pipe.process_event(_b_event(bars))
    assert out_b["status"] == "RECORDED"  # 1m watermark now at the B candle
    # A Strategy A alert OLDER than the Strategy B candle still journals:
    # the watermark key includes the strategy.
    out_a = pipe.process_event(
        _a_event(received_at=_iso(datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) + timedelta(seconds=30)))
    )
    assert out_a["status"] == "RECORDED"
    assert store.count() == 2
    assert store.rejection_count() == 0


# --- Group B: Strategy A/B field isolation ---------------------------------

def test_group_b_a_record_carries_no_b_artifacts(tmp_path):
    now = datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) + timedelta(seconds=30)
    pipe, _ = _pipeline(tmp_path, now)
    # Alert deliberately supplies NO level and NO bias: nothing may be
    # filled in from Strategy B concepts (ranges, detector vocabulary).
    rec = pipe.process_event(_a_event())["record"]
    gates = rec["classification"]["gate_results"]
    assert set(gates) == {f"G{i}" for i in range(1, 7)}
    assert not any(k.startswith("R") for k in gates)  # no Bot B rule keys
    ms = rec["market_state"]
    assert ms["gate_source"] == "tradingview_alert_payload"  # A-native stamp
    assert "data_label" not in ms  # Bot B detector field
    assert ms["confirmed_sr_level"] is None  # no range-derived level invented
    assert ms["bias_5m"] is None  # no B bias vocabulary leaked in
    assert rec["strategy_version"] == sc.STRATEGY_A_VERSION
    assert rec["risk"]["exit_conditions"] is None  # no B exit text inherited
    assert rec["risk"]["risk_approval_status"] == "UNAPPROVED"
    assert rec["risk"]["quantity"] is None


def test_group_b_b_record_carries_no_a_artifacts(tmp_path):
    bars = _long_fixture()
    pipe, _ = _pipeline(tmp_path, _last_bar_dt(bars) + timedelta(seconds=30))
    rec = pipe.process_event(_b_event(bars))["record"]
    gates = rec["classification"]["gate_results"]
    assert set(gates) == {f"R{i}" for i in range(1, 8)}
    assert not any(k.startswith("G") for k in gates)  # no Six Gates keys
    ms = rec["market_state"]
    assert "gate_source" not in ms  # no alert-source stamp
    assert ms["data_quality"] == "EVALUATED"  # B-native; A uses ALERT_REPORTED
    assert rec["strategy_version"] == "MQU-SB-001 v1.0"
    assert rec["risk"]["exit_conditions"] == EXITS


def _subset(rec):
    return {
        "strategy_id": rec["strategy_id"],
        "strategy_version": rec["strategy_version"],
        "timeframe": rec["timeframe"],
        "gate_results": rec["classification"]["gate_results"],
        "classification": rec["classification"]["classification"],
        "qualification_status": rec["classification"]["qualification_status"],
        "price": rec["market_state"]["price"],
        "bias_5m": rec["market_state"]["bias_5m"],
        "vwap": rec["market_state"]["vwap"],
        "risk_approval_status": rec["risk"]["risk_approval_status"],
        "quantity": rec["risk"]["quantity"],
    }


def test_group_b_shared_store_no_cross_contamination(tmp_path):
    bars = _long_fixture()
    b_ev = _b_event(bars)
    a_ev = _a_event(
        received_at=_iso(datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) + timedelta(seconds=30))
    )
    now_b = _last_bar_dt(bars) + timedelta(seconds=30)

    # Each event alone in its own store.
    store_b = sp.SignalStore(str(tmp_path / "only_b.db"))
    rec_b_solo = sp.SignalPipeline(store_b, now_fn=lambda: now_b).process_event(b_ev)["record"]
    store_a = sp.SignalStore(str(tmp_path / "only_a.db"))
    now_a = datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) + timedelta(seconds=30)
    rec_a_solo = sp.SignalPipeline(store_a, now_fn=lambda: now_a).process_event(a_ev)["record"]

    # Both events in one shared store.
    store = sp.SignalStore(str(tmp_path / "shared.db"))
    pipe = sp.SignalPipeline(store, now_fn=lambda: now_b)
    rec_b_shared = pipe.process_event(b_ev)["record"]
    rec_a_shared = pipe.process_event(a_ev)["record"]
    assert store.count() == 2

    # Re-read from the journal itself: neither record changed by the
    # other's presence.
    jour_b = store.get_by_idempotency_key(rec_b_shared["idempotency_key"])
    jour_a = store.get_by_idempotency_key(rec_a_shared["idempotency_key"])
    assert _subset(jour_b) == _subset(rec_b_solo)
    assert _subset(jour_a) == _subset(rec_a_solo)
    assert jour_b["strategy_id"] == "STRATEGY_B" and jour_a["strategy_id"] == "STRATEGY_A"
