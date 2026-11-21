"""Paper bridge — end-to-end acceptance tests (paper-readiness mission).

The full chain, exercised with real components only:

    market event → SignalPipeline → canonical record → Analyst review
    (Command tree) → bridge risk validation → Stage 2 paper engine →
    bridge journal → status surface

No component is mocked: the pipeline, the Analyst consumer, and the
Stage 2 engine are the real modules; the engine's Mongo is the same
mongomock arrangement Stage 2's own suite uses (no MongoDB runs
locally). Event/bar fixtures mirror the Phase 2 battery's deterministic
shapes. Every test asserts journal contents, not just return values.

Offline: a placeholder MONGO_URL is set before importing server (the
motor client is lazy and is rebound by the bridge before any use).
"""

import copy
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:1")  # never contacted

import paper_bridge as pb  # noqa: E402
import signal_contract as sc  # noqa: E402
import signal_pipeline as sp  # noqa: E402

T0 = (1_700_000_000 // 900) * 900
EXITS = "PAPER: exit on close back through the boundary"
FULL_A_GATES = {f"G{i}": "PASS" for i in range(1, 7)}
LABEL = "DETERMINISTIC_FALLBACK — PROVIDER_NOT_CONNECTED"


# ---------------------------------------------------------------------------
# Event fixtures (mirroring the Phase 2 battery's deterministic shapes)
# ---------------------------------------------------------------------------

def _bar(t, o, h, l, c, v=100):
    return {"time": t, "open": o, "high": h, "low": l, "close": c, "volume": v}


def _long_fixture():
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
    return [_bar(T0 + i * 60, price, price + 0.4, price - 0.4, price, 100)
            for i in range(n)]


def _last_dt(bars):
    return datetime.fromtimestamp(bars[-1]["time"], tz=timezone.utc)


def _b_event(bars, **over):
    ev = dict(
        event_kind="strategy_b", contract="MNQZ6",
        data_provider="FIXTURE — synthetic bars, no live feed",
        data_source="test_fixture", bars_1m=bars,
        range_high=130, range_low=85, risk_limit_dollars=500,
        exit_conditions=EXITS, approved=True,
    )
    ev.update(over)
    return ev


def _a_event(**alert_over):
    alert = dict(
        direction="LONG", price=26100.0, bar_time=T0 + 3600,
        candle_closed=True, gate_results=dict(FULL_A_GATES),
        vwap=26080.0, ema9=26095.0, ema21=26085.0, rsi14=58.0,
        level=26050.0,
    )
    alert.update(alert_over)
    return dict(
        event_kind="strategy_a", contract="MNQZ6",
        data_provider="TradingView (alert payload)",
        data_source="tradingview_alert", alert=alert,
    )


# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

class Harness:
    def __init__(self, tmp_path):
        self.dir = tmp_path
        self.store = sp.SignalStore(str(tmp_path / "signals.db"))
        self.bridge = pb.PaperBridge(
            db_path=str(tmp_path / "bridge.db"),
            signal_store_path=str(tmp_path / "signals.db"))

    def pipeline_at(self, dt):
        return sp.SignalPipeline(self.store, now_fn=lambda: dt)

    def b_record(self, bars=None):
        bars = bars if bars is not None else _long_fixture()
        pipe = self.pipeline_at(_last_dt(bars) + timedelta(seconds=30))
        out = pipe.process_event(_b_event(bars))
        return out

    def a_record(self, **alert_over):
        now = datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) \
            + timedelta(seconds=30)
        out = self.pipeline_at(now).process_event(_a_event(**alert_over))
        return out

    def reset_cooldown(self):
        """Test-fixture state control, the same pattern Stage 2's own
        suite uses: the engine's 1500 ms order cooldown is a real
        safety control and the bridge never bypasses it; tests that
        execute twice in one session reset the clock directly."""
        self.bridge.server._operator_state["last_order_at"] = 0.0

    def close(self):
        self.bridge.close()
        self.store.close()


@pytest.fixture()
def harness(tmp_path):
    h = Harness(tmp_path)
    yield h
    h.close()


def _journal_kinds(bridge):
    return [e["bridge"].get("reason") if e.get("action") == "REJECTED"
            else e.get("action") for e in bridge.journal_entries()]


# ---------------------------------------------------------------------------
# Happy paths — Strategy B executes under its founder-approved paper
# profile (Nov 21, 2026); Strategy A is held attended-only.
#
# SPEC CHANGE (founder decision, Nov 21, 2026): before this decision
# the suite executed a Strategy A record end-to-end with a 1R-derived
# target and derived Strategy B's target the same way. The founder's
# B-only automation scope replaces that spec: A records are HELD
# (reviewed + journaled, never auto-executed) and B's target is the
# opposite range boundary from the record's own range fields, under a
# $200 planned-risk cap including estimated fees/slippage.
# ---------------------------------------------------------------------------

def test_b_valid_qualification_full_chain(harness):
    out = harness.b_record()
    assert out["status"] == "RECORDED" and out["order_created"] is False
    rec = out["record"]
    assert rec["classification"]["qualification_status"] == "qualified"

    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "EXECUTED"
    order = res["order"]
    # Fill is the record's own price, marked SIMULATED; brackets are
    # the record's structural stop (85.0, used exactly as recorded) and
    # the opposite range boundary as target (range_high 130.0 — the
    # founder-approved B profile; NOT the old 1R derivation, 123.0).
    assert order["fill_price"] == pytest.approx(rec["risk"]["proposed_entry"], abs=0.01)
    assert order["fill_price_source"] == "SIMULATED"
    assert order["sl_price"] == pytest.approx(85.0)
    assert order["tp_price"] == pytest.approx(130.0)
    assert order["qty"] == pb.PAPER_PROFILE_QTY == 1
    assert order["phase"] == "SIM_LOG_ONLY"
    assert order["resulting_position"]["side"] == "LONG"
    assert res["review"]["disposition"] in pb.PROCEEDING_DISPOSITIONS
    assert res["review"]["explanation_source"] == LABEL
    # The journal carries the planned-risk breakdown: 76 stop ticks
    # x $0.50 = $38.00 + $4.00 est. fees + $1.00 est. slippage = $43.00,
    # within the $200.00 cap.
    planned = res["risk_decision"]["planned_risk"]
    assert planned == {"stop_ticks": 76, "stop_dollars": 38.0,
                       "est_fees": 4.0, "est_slippage": 1.0,
                       "total": 43.0, "cap_dollars": 200.0,
                       "within_cap": True}
    assert res["risk_decision"]["target"] == 130.0
    # Reproducibility: the stored execution carries the full inputs.
    stored = harness.bridge._get_execution(rec["signal_id"])
    assert stored["record"] == rec
    assert stored["review"]["signal_id"] == rec["signal_id"]
    assert stored["risk_decision"]["risk_approval_status"] == "UNAPPROVED"
    assert stored["risk_decision"]["outcome"] == "EXECUTED"
    assert stored["risk_decision"]["planned_risk"]["total"] == 43.0


def test_a_valid_alert_held_attended_only(harness):
    # SPEC CHANGE (founder decision, Nov 21, 2026): this test previously
    # executed the A record end-to-end. Automation scope is now
    # Strategy B only — a qualified, Analyst-passed A record is
    # reviewed and journaled as HELD_ATTENDED_ONLY and never
    # auto-executed, whatever the automation state (the hold is
    # presented here BEFORE any resume, and again after it).
    out = harness.a_record(structural_stop=26050.0)
    rec = out["record"]
    assert rec["classification"]["qualification_status"] == \
        "qualified_alert_reported"
    assert set(rec["classification"]["gate_results"]) == \
        {f"G{i}" for i in range(1, 7)}

    res = harness.bridge.execute_record(rec)
    assert res["status"] == "HELD"
    assert res["reason"] == pb.R_HELD_ATTENDED
    # The Analyst gate ran before the hold, and its review is journaled.
    assert res["review"]["disposition"] in pb.PROCEEDING_DISPOSITIONS
    assert res["review"]["explanation_source"] == LABEL
    # No position, no order, and the hold is the stored outcome.
    assert harness.bridge.status()["paper"]["position"]["side"] is None
    stored = harness.bridge._get_execution(rec["signal_id"])
    assert stored["status"] == "HELD"
    assert stored["reason"] == pb.R_HELD_ATTENDED
    assert stored["review"]["signal_id"] == rec["signal_id"]
    kinds = [e["action"] for e in harness.bridge.journal_entries()]
    assert "HELD_ATTENDED_ONLY" in kinds

    # Resuming automation does not change A's disposition: a fresh A
    # record (a later alert candle -> a new signal) is held again,
    # not executed.
    harness.bridge.set_automation_paused(False)
    now2 = datetime.fromtimestamp(T0 + 7200, tz=timezone.utc) \
        + timedelta(seconds=30)
    out2 = harness.pipeline_at(now2).process_event(
        _a_event(structural_stop=26050.0, bar_time=T0 + 7200))
    assert out2["record"]["signal_id"] != rec["signal_id"]
    res2 = harness.bridge.execute_record(out2["record"])
    assert res2["status"] == "HELD"
    assert harness.bridge.status()["paper"]["position"]["side"] is None


def test_a_and_b_paths_independent_and_isolated(harness):
    harness.bridge.set_automation_paused(False)
    # A is held — it neither takes the engine's single position nor is
    # blocked by it; B then executes independently.
    a_out = harness.a_record(structural_stop=26050.0)
    res_a = harness.bridge.execute_record(a_out["record"])
    assert res_a["status"] == "HELD"

    b_out = harness.b_record()
    res_b = harness.bridge.execute_record(b_out["record"])
    assert res_b["status"] == "EXECUTED"
    # Close the B position at its opposite-boundary target (130.0).
    exit_b = harness.bridge.on_price(130.5)
    assert exit_b["exit_reason"] == "TAKE_PROFIT"

    a_stored = harness.bridge._get_execution(a_out["record"]["signal_id"])
    b_stored = harness.bridge._get_execution(b_out["record"]["signal_id"])
    assert a_stored["strategy_id"] == "STRATEGY_A"
    assert b_stored["strategy_id"] == "STRATEGY_B"
    # Field isolation through the bridge: A gates are G-keys only,
    # B gates are R-keys only; neither record carries the other's fields.
    assert set(a_stored["record"]["classification"]["gate_results"]) == \
        {f"G{i}" for i in range(1, 7)}
    assert set(b_stored["record"]["classification"]["gate_results"]) == \
        {f"R{i}" for i in range(1, 8)}
    assert a_stored["status"] == "HELD"
    assert b_stored["status"] == "CLOSED"


# ---------------------------------------------------------------------------
# Ingestion rejections (pipeline level — the chain refuses bad input)
# ---------------------------------------------------------------------------

def test_invalid_instrument_rejected(harness):
    pipe = harness.pipeline_at(
        _last_dt(_long_fixture()) + timedelta(seconds=30))
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_b_event(_long_fixture(), instrument="ES"))
    assert harness.store.count() == 0


def test_missing_and_invalid_price_rejected(harness):
    now = datetime.fromtimestamp(T0 + 3600, tz=timezone.utc) \
        + timedelta(seconds=30)
    pipe = harness.pipeline_at(now)
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_a_event(price=None))
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_a_event(price="26100"))
    with pytest.raises(sc.SignalValidationError):
        pipe.process_event(_a_event(price=-26100.0))
    assert harness.store.count() == 0


def test_out_of_order_rejected_no_state_regression(harness):
    bars = _long_fixture()
    out = harness.b_record(bars)
    assert out["status"] == "RECORDED"
    first_id = out["record"]["signal_id"]

    # An older event (bars shifted one hour earlier) must not journal.
    older = [_bar(b["time"] - 3600, b["open"], b["high"], b["low"],
                  b["close"], b["volume"]) for b in bars]
    pipe = harness.pipeline_at(_last_dt(older) + timedelta(seconds=30))
    out2 = pipe.process_event(_b_event(older))
    assert out2["record"]["classification"]["rejection_status"] == \
        "OUT_OF_ORDER"
    assert harness.store.count() == 1
    latest = harness.store.latest_qualified("STRATEGY_B", "MNQ")
    assert latest["signal_id"] == first_id


# ---------------------------------------------------------------------------
# Bridge-level rejections — every one journaled
# ---------------------------------------------------------------------------

def test_duplicate_signal_creates_no_second_position(harness):
    out = harness.b_record()
    rec = out["record"]
    harness.bridge.set_automation_paused(False)
    assert harness.bridge.execute_record(rec)["status"] == "EXECUTED"
    dup = harness.bridge.execute_record(rec)
    assert dup["status"] == "DUPLICATE"
    assert dup["execution"]["signal_id"] == rec["signal_id"]
    status = harness.bridge.status()
    execs = status["paper"]["executions"]
    assert len(execs) == 1
    assert status["paper"]["position"]["qty"] == 1
    kinds = [e["action"] for e in harness.bridge.journal_entries()]
    assert "DUPLICATE_SIGNAL" in kinds


def test_paused_automation_rejection_journaled_then_resume_executes(harness):
    out = harness.b_record()
    rec = out["record"]
    # Default state: automation paused (Stage 2 default OFF).
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "REJECTED"
    assert res["reason"] == pb.R_AUTOMATION_PAUSED
    assert harness.bridge.status()["paper"]["position"]["side"] is None
    kinds = _journal_kinds(harness.bridge)
    assert pb.R_AUTOMATION_PAUSED in kinds
    # State-dependent rejection: after an explicit resume, the same
    # signal re-presented is evaluated on its merits. Both attempts
    # remain in the journal.
    harness.bridge.set_automation_paused(False)
    res2 = harness.bridge.execute_record(rec)
    assert res2["status"] == "EXECUTED"
    assert len(harness.bridge.journal_entries()) >= 2


def test_risk_bound_exceeded_journaled(harness):
    # SPEC CHANGE (founder decision, Nov 21, 2026): this test previously
    # drove Stage 2's bracket ceiling through a Strategy A record; A is
    # now held before risk validation, so the ceiling is exercised on
    # the B path — a record whose STOP is comfortably inside the $200
    # cap (100 ticks = $55.00 planned) but whose opposite-boundary
    # TARGET sits 480 ticks away (> MAX_BRACKET_TICKS 400).
    out = harness.b_record()
    rec = copy.deepcopy(out["record"])
    rec["risk"]["proposed_entry"] = 200.0
    rec["risk"]["structural_stop"] = 175.0
    rec["risk"]["stop_distance_points"] = 25.0
    rec["market_state"]["price"] = 200.0
    rec["market_state"]["range_high"] = 320.0
    rec["market_state"]["range_low"] = 170.0
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "REJECTED"
    assert res["reason"] == pb.R_RISK_BOUND
    assert harness.bridge.status()["paper"]["position"]["side"] is None


def test_missing_exit_framework_rejected(harness):
    # A genuine pipeline-qualified A record whose alert carried NO
    # structural stop. Under the pre-Nov-21 spec the bridge rejected
    # it with EXIT_FRAMEWORK_MISSING; under the founder's B-only scope
    # it is HELD first — A never reaches exit validation.
    out = harness.a_record()
    rec = out["record"]
    assert rec["classification"]["qualification_status"] == \
        "qualified_alert_reported"
    assert rec["risk"]["structural_stop"] is None
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "HELD"
    assert res["reason"] == pb.R_HELD_ATTENDED

    # On the B path the defense is unchanged: a qualified record
    # stripped of its stop after journaling is refused by the bridge
    # itself — no stop, no planned risk, no bracket.
    b_out = harness.b_record()
    stripped = copy.deepcopy(b_out["record"])
    stripped["risk"]["structural_stop"] = None
    stripped["risk"]["stop_distance_points"] = None
    res_b = harness.bridge.execute_record(stripped)
    assert res_b["status"] == "REJECTED"
    assert res_b["reason"] == pb.R_EXIT_MISSING


def test_analyst_contradiction_blocks_execution(harness):
    out = harness.b_record()
    rec = copy.deepcopy(out["record"])
    # Mutate the record into self-contradiction: LONG while the 5m bias
    # resolves down and price sits below VWAP (battery scenario 18's
    # mutation, applied to a fresh record).
    rec["market_state"]["bias_5m"] = "not aligned"
    rec["market_state"]["vwap"] = {"value": 120.0,
                                   "relationship": "price below VWAP"}
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "REJECTED"
    assert res["reason"] == pb.R_ANALYST_BLOCKED
    assert res["review"]["disposition"] == "CONTRADICTION_DETECTED"
    assert res["review"]["reclassified"] is False
    assert harness.bridge.status()["paper"]["position"]["side"] is None


def test_not_qualified_record_rejected_by_bridge(harness):
    bars = _flat_fixture()
    pipe = harness.pipeline_at(_last_dt(bars) + timedelta(seconds=30))
    out = pipe.process_event(_b_event(bars))
    rec = out["record"]
    # The B adapter's non-qualified status for a flat, range-less tape is
    # "awaiting_data_or_range" — any non-qualified status must be refused.
    assert rec["classification"]["qualification_status"] != "qualified"
    assert rec["classification"]["classification"] == "NO_TRADE"
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "REJECTED"
    assert res["reason"] == pb.R_NOT_QUALIFIED


def test_second_signal_blocked_while_position_open(harness):
    # The Stage 2 engine holds ONE position: a second qualified B
    # signal arriving while a B position is open is rejected, never
    # merged into the same book. (Under the pre-Nov-21 spec this test
    # used a Strategy A record as the second signal; A is now held
    # before it can ever reach this gate, so the second signal here is
    # a re-identified copy of the qualified B record — the same
    # post-journaling record handling this suite already uses for the
    # Analyst-contradiction case.)
    harness.bridge.set_automation_paused(False)
    b_out = harness.b_record()
    assert harness.bridge.execute_record(b_out["record"])["status"] == \
        "EXECUTED"
    second = copy.deepcopy(b_out["record"])
    second["signal_id"] = "second-signal-while-open"
    res = harness.bridge.execute_record(second)
    assert res["status"] == "REJECTED"
    assert res["reason"] == pb.R_POSITION_OPEN
    assert harness.bridge.status()["paper"]["position"]["qty"] == 1


# ---------------------------------------------------------------------------
# Failure behavior
# ---------------------------------------------------------------------------

def test_provider_absent_chain_completes_deterministically(harness):
    # No provider is connected anywhere in this system; the chain must
    # complete on the deterministic fallback, labeled verbatim.
    out = harness.b_record()
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(out["record"])
    assert res["status"] == "EXECUTED"
    assert res["review"]["explanation_source"] == LABEL
    status = harness.bridge.status()
    assert status["analyst"]["provider_status"] == "NOT_CONNECTED"
    assert status["connectivity"]["provider"] == "NOT_CONNECTED"
    assert status["analyst"]["explanation_source"] == LABEL


def test_pipeline_persistence_failure_fails_closed(tmp_path):
    class FailingStore(sp.SignalStore):
        def put(self, rec):
            raise sp.PersistenceError("injected journal failure")

    store = FailingStore(str(tmp_path / "signals.db"))
    bars = _long_fixture()
    pipe = sp.SignalPipeline(
        store, now_fn=lambda: _last_dt(bars) + timedelta(seconds=30))
    with pytest.raises(sp.PipelinePersistenceError):
        pipe.process_event(_b_event(bars))
    assert store.count() == 0
    store.close()


def test_pipeline_firewall_intact():
    # The pipeline itself must never gain an execution path: the bridge
    # is a separate consumer, and signal_pipeline imports neither the
    # bridge nor the engine's execution core.
    src = open(os.path.join(os.path.dirname(__file__), "..",
                            "signal_pipeline.py")).read()
    assert "paper_bridge" not in src
    assert "_execute_order" not in src
    assert "import server" not in src


# ---------------------------------------------------------------------------
# Recovery / replay
# ---------------------------------------------------------------------------

def test_recovery_and_replay_after_restart(tmp_path):
    h1 = Harness(tmp_path)
    out = h1.b_record()
    rec = out["record"]
    h1.bridge.set_automation_paused(False)
    assert h1.bridge.execute_record(rec)["status"] == "EXECUTED"
    journal_before = len(h1.bridge.journal_entries())
    h1.close()

    # Restart: a new bridge over the SAME journal DBs.
    h2 = Harness(tmp_path)
    status = h2.bridge.status()
    assert status["paper"]["position"]["side"] == "LONG"
    assert status["paper"]["position"]["qty"] == 1
    execs = status["paper"]["executions"]
    assert len(execs) == 1 and execs[0]["status"] == "OPEN"

    # Replay creates nothing new: same record -> DUPLICATE, same event
    # -> pipeline DUPLICATE, counts unchanged.
    assert h2.bridge.execute_record(rec)["status"] == "DUPLICATE"
    pipe = h2.pipeline_at(_last_dt(_long_fixture()) + timedelta(seconds=30))
    out2 = pipe.process_event(_b_event(_long_fixture()))
    assert out2["status"] == "DUPLICATE"
    assert h2.store.count() == 1
    assert len(h2.bridge.status()["paper"]["executions"]) == 1

    # The rehydrated position still exits through the engine (target
    # is now the opposite range boundary, 130.0).
    exit_entry = h2.bridge.on_price(130.5)
    assert exit_entry["exit_reason"] == "TAKE_PROFIT"
    assert h2.bridge.status()["paper"]["executions"][0]["status"] == \
        "CLOSED"
    assert len(h2.bridge.journal_entries()) > journal_before
    h2.close()


# ---------------------------------------------------------------------------
# Dashboard surface consistency
# ---------------------------------------------------------------------------

def test_status_endpoint_matches_journal(harness, monkeypatch):
    import paper_bridge_api
    from fastapi.testclient import TestClient
    import server

    out = harness.b_record()
    harness.bridge.set_automation_paused(False)
    harness.bridge.execute_record(out["record"])
    monkeypatch.setattr(paper_bridge_api, "_bridge", harness.bridge)

    client = TestClient(server.app)
    resp = client.get("/api/paper-bridge/status")
    assert resp.status_code == 200
    body = resp.json()

    direct = harness.bridge.status()
    assert body["paper"]["journal_entries"] == \
        direct["paper"]["journal_entries"] == \
        len(harness.bridge.journal_entries())
    assert len(body["paper"]["executions"]) == \
        len(direct["paper"]["executions"]) == 1
    assert body["paper"]["executions"][0]["signal_id"] == \
        out["record"]["signal_id"]
    assert body["risk"]["risk_approval_status"] == "UNAPPROVED"
    # The founder-approved Strategy B paper profile is on the surface,
    # stated as paper parameters.
    b_profile = body["risk"]["strategy_b_paper_profile"]
    assert b_profile["risk_cap_dollars"] == 200.0
    assert b_profile["qty"] == 1
    assert b_profile["est_fees_round_trip_dollars"] == 4.0
    assert b_profile["est_slippage_dollars"] == 1.0
    assert "opposite 15-minute range boundary" in b_profile["target_rule"]
    assert "16:00 ET" in b_profile["time_exit"]
    assert body["risk"]["automation_paused"] is False
    assert body["analyst"]["provider_status"] == "NOT_CONNECTED"
    assert body["pipeline"]["records_journaled"] == 1
    # The surface must never claim a state the system has not earned.
    import json as _json
    blob = _json.dumps(body)
    for forbidden in ("\"LIVE\"", "\"EXECUTING\"", "\"PROFITABLE\"",
                      "\"CONNECTED\""):
        assert forbidden not in blob


# ---------------------------------------------------------------------------
# Founder-approved Strategy B paper profile (Nov 21, 2026)
#
# Planned risk = stop ticks x $0.50 (MNQ tick value, qty 1) + $4.00
# estimated round-trip fees + $1.00 estimated slippage (2 ticks);
# cap $200.00. The stop is used exactly as recorded; an over-cap
# setup is rejected and journaled, never resized.
# ---------------------------------------------------------------------------

def _b_record_with(harness, *, entry, stop, range_low, range_high,
                   bars=None):
    """A genuine pipeline-qualified B record re-based to the given
    entry/stop/range shape (post-journaling record handling — the
    same pattern the Analyst-contradiction test uses)."""
    out = harness.b_record(bars)
    rec = copy.deepcopy(out["record"])
    rec["risk"]["proposed_entry"] = entry
    rec["risk"]["structural_stop"] = stop
    rec["risk"]["stop_distance_points"] = abs(entry - stop)
    rec["market_state"]["price"] = entry
    rec["market_state"]["range_low"] = range_low
    rec["market_state"]["range_high"] = range_high
    return rec


def _short_bars():
    """The long fixture mirrored around 215.0: a genuine SHORT setup
    at the upper boundary of the same 85-130 range."""
    c = 215.0
    return [_bar(b["time"], c - b["open"], c - b["low"], c - b["high"],
                 c - b["close"], b["volume"]) for b in _long_fixture()]


def test_b_profile_accept_301_tick_long(harness):
    # The measured shape: a 301-tick stop = $150.50 + $5.00 estimates
    # = $155.50 planned risk, inside the $200.00 cap.
    rec = _b_record_with(harness, entry=160.25, stop=85.0,
                         range_low=85.0, range_high=200.0)
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "EXECUTED"
    planned = res["risk_decision"]["planned_risk"]
    assert planned["stop_ticks"] == 301
    assert planned["stop_dollars"] == 150.50
    assert planned["total"] == 155.50
    assert planned["within_cap"] is True
    order = res["order"]
    # Stop exactly as recorded — never widened or narrowed to fit.
    assert order["sl_price"] == 85.0
    # Target is the opposite boundary (range high), from the record.
    assert order["tp_price"] == 200.0
    assert order["tp_ticks"] == 159
    assert order["qty"] == 1


def test_b_profile_accept_301_tick_short(harness):
    rec = _b_record_with(harness, entry=100.0, stop=175.25,
                         range_low=60.0, range_high=176.0,
                         bars=_short_bars())
    assert rec["classification"]["classification"] == "SHORT"
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "EXECUTED"
    planned = res["risk_decision"]["planned_risk"]
    assert planned["stop_ticks"] == 301
    assert planned["total"] == 155.50
    order = res["order"]
    assert order["sl_price"] == 175.25  # stop exactly as recorded
    # Target is the opposite boundary for a SHORT: the range low.
    assert order["tp_price"] == 60.0
    assert order["resulting_position"]["side"] == "SHORT"


def test_b_profile_boundary_exactly_at_cap_accepted(harness):
    # 390 stop ticks x $0.50 = $195.00 + $5.00 estimates = exactly
    # $200.00 planned — at the cap is within the cap.
    rec = _b_record_with(harness, entry=200.0, stop=102.5,
                         range_low=100.0, range_high=260.0)
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "EXECUTED"
    planned = res["risk_decision"]["planned_risk"]
    assert planned["stop_ticks"] == 390
    assert planned["total"] == 200.00
    assert planned["within_cap"] is True
    assert res["order"]["sl_price"] == 102.5
    assert res["order"]["tp_price"] == 260.0


def test_b_profile_over_cap_rejected_and_journaled(harness):
    # One tick past the boundary case: 391 stop ticks = $195.50 +
    # $5.00 = $200.50 planned — over the cap, so the setup is
    # rejected with the computed total stated, never resized.
    rec = _b_record_with(harness, entry=200.0, stop=102.25,
                         range_low=100.0, range_high=260.0)
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "REJECTED"
    assert res["reason"] == pb.R_RISK_CAP
    assert res["risk_decision"]["planned_risk"]["total"] == 200.50
    assert res["risk_decision"]["planned_risk"]["within_cap"] is False
    assert "$200.50" in res["risk_decision"]["detail"]
    # Journaled with the breakdown; no position was taken.
    stored = harness.bridge._get_execution(rec["signal_id"])
    assert stored["status"] == "REJECTED"
    assert stored["reason"] == pb.R_RISK_CAP
    assert stored["risk_decision"]["planned_risk"]["stop_dollars"] == \
        195.50
    assert pb.R_RISK_CAP in _journal_kinds(harness.bridge)
    assert harness.bridge.status()["paper"]["position"]["side"] is None


def test_b_profile_missing_range_data_rejected(harness):
    # A qualified B record without the range fields its exit
    # framework needs: rejected, and no target is invented — the
    # bridge never falls back to a derived R target for Strategy B.
    out = harness.b_record()
    rec = copy.deepcopy(out["record"])
    rec["market_state"]["range_high"] = None
    rec["market_state"]["range_low"] = None
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(rec)
    assert res["status"] == "REJECTED"
    assert res["reason"] == pb.R_EXIT_MISSING
    assert "target" not in res["risk_decision"]
    assert harness.bridge.status()["paper"]["position"]["side"] is None


def test_b_profile_time_exit_at_1600_et(harness):
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")

    out = harness.b_record()
    rec = out["record"]
    harness.bridge.set_automation_paused(False)
    assert harness.bridge.execute_record(rec)["status"] == "EXECUTED"
    # The fixture record's session date is 2023-11-14 (ET). A price
    # between the brackets (85 / 130) moves nothing on its own...
    assert harness.bridge.on_price(110.0) is None  # no timestamp given
    # ...nor does a timestamp before 16:00 ET on the session date.
    assert harness.bridge.on_price(
        110.0, ts=datetime(2023, 11, 14, 15, 59, tzinfo=et)) is None
    assert harness.bridge.status()["paper"]["position"]["side"] == "LONG"
    # At 16:00 ET the still-open B position closes at the update's
    # price, journaled as TIME_EXIT.
    exit_entry = harness.bridge.on_price(
        110.0, ts=datetime(2023, 11, 14, 16, 0, tzinfo=et))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["fill_price"] == 110.0
    assert exit_entry["fill_price_source"] == "SIMULATED"
    assert exit_entry["exit_pnl"] == 12.0  # (110 - 104) x 1 x $2
    assert exit_entry["time_exit"]["session_date"] == "2023-11-14"
    status = harness.bridge.status()
    assert status["paper"]["position"]["side"] is None
    assert status["paper"]["executions"][0]["status"] == "CLOSED"
    assert status["paper"]["executions"][0]["exit"]["exit_reason"] == \
        "TIME_EXIT"
