"""Paper bridge — Amendment A1 time-exit mechanisms (Nov 21, 2026).

The two-path proof from Amendment A1 §A1.4 of the Render migration
readiness package, adapted for Gate 2A: the staleness threshold
(P-A1-1) and the recovery window (P-A1-2) are PROPOSED, not decided,
so both ship UNSET. Where a path needs a window or a threshold, the
test INJECTS it as a constructor parameter — an injected value is a
test fixture proving the parameterized branch, never a product
default, and the shipped-default paths (2b) are tested as they ship.

    Path 1 — service running at the deadline (Mechanism 1, the
             clock-driven scheduled exit).
    Path 2 — restart spanning the deadline (Mechanism 2, startup
             recovery): 2a deadline price recoverable · 2b not
             recoverable (the shipped default) · 2c restart returns
             before the deadline.

Everything runs on the acceptance suite's Harness — the real
pipeline, Analyst consumer, and Stage 2 engine; nothing is mocked.
The fixture record's session date is 2023-11-14 (ET); its brackets
are 85.0 (stop) / 130.0 (target) and its entry is 104.0, so prices
between the brackets move nothing on their own.
"""

import copy
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:1")  # never contacted

import paper_bridge as pb  # noqa: E402

ET = ZoneInfo("America/New_York")
SESSION = (2023, 11, 14)  # the acceptance fixture's session date (ET)


def _et(hour, minute, day=SESSION[2], month=SESSION[1], year=SESSION[0]):
    return datetime(year, month, day, hour, minute, tzinfo=ET)


def _load_module(name, filename):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


acc = _load_module("pb_acceptance_for_time_exit",
                   "test_paper_bridge_acceptance.py")
Harness = acc.Harness


def _restart(h, **bridge_kw):
    """Close the harness's bridge and construct a new one over the
    SAME journal DBs — the established restart pattern — with any
    Amendment A1 parameters / clock seams injected."""
    db_path = h.bridge.db_path
    store_path = str(h.dir / "signals.db")
    h.bridge.close()
    h.bridge = pb.PaperBridge(db_path=db_path,
                              signal_store_path=store_path,
                              **bridge_kw)
    return h.bridge


def _replace_bridge(h, **bridge_kw):
    """Swap the harness's (fresh) bridge for a parameterized one over
    the same empty DBs, before any record is executed."""
    return _restart(h, **bridge_kw)


def _execute_b(h):
    out = h.b_record()
    h.bridge.set_automation_paused(False)
    res = h.bridge.execute_record(out["record"])
    assert res["status"] == "EXECUTED"
    return out["record"]


def _recovery_events(bridge):
    return [e["bridge"]["recovery_block"]["event"]
            for e in bridge.journal_entries()
            if e.get("action") == "RECOVERY_BLOCK"]


@pytest.fixture()
def harness(tmp_path):
    h = Harness(tmp_path)
    yield h
    h.close()


# ---------------------------------------------------------------------------
# Path 1 — service running at the deadline (Mechanism 1)
# ---------------------------------------------------------------------------

def test_path1_scheduler_fires_at_1600_et(harness):
    _execute_b(harness)
    # Supply a price through the tape at 15:30 ET (between brackets).
    assert harness.bridge.on_price(110.0, ts=_et(15, 30)) is None
    # 15:59 ET: no fire, position untouched.
    assert harness.bridge.tick_time_exit(_et(15, 59)) is None
    assert harness.bridge.status()["paper"]["position"]["side"] == "LONG"
    # 16:00 ET: the scheduled exit fires at the most recent supplied
    # price, with the price's source timestamp and age journaled. The
    # staleness threshold ships UNSET (Gate 2A): the age is a plain
    # fact, the threshold is recorded NOT_SET, and NO stale/not-stale
    # verdict is journaled.
    exit_entry = harness.bridge.tick_time_exit(_et(16, 0))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["fill_price"] == 110.0
    assert exit_entry["fill_price_source"] == "SIMULATED"
    evidence = exit_entry["time_exit"]
    assert evidence["mechanism"] == "SCHEDULED"
    assert evidence["session_date"] == "2023-11-14"
    assert evidence["price_source_ts"] == _et(15, 30).isoformat()
    assert evidence["price_age_seconds"] == 1800.0
    assert evidence["staleness_threshold"] == "NOT_SET"
    assert "stale" not in evidence
    status = harness.bridge.status()
    assert status["paper"]["position"]["side"] is None
    assert status["paper"]["executions"][0]["status"] == "CLOSED"
    # A later tick finds no open position: no double fire.
    assert harness.bridge.tick_time_exit(_et(16, 5)) is None


def test_path1_staleness_verdict_only_when_threshold_injected(tmp_path):
    # P-A1-1 injected BY THE TEST (900 s): an older price is journaled
    # stale, a fresher one is not — and the exit fires either way.
    h = Harness(tmp_path / "stale")
    _replace_bridge(h, staleness_threshold_seconds=900)
    _execute_b(h)
    assert h.bridge.on_price(110.0, ts=_et(15, 30)) is None
    exit_entry = h.bridge.tick_time_exit(_et(16, 0))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["time_exit"]["stale"] is True
    assert exit_entry["time_exit"]["staleness_threshold_seconds"] == 900.0
    assert exit_entry["time_exit"]["price_age_seconds"] == 1800.0
    h.close()

    h = Harness(tmp_path / "fresh")
    _replace_bridge(h, staleness_threshold_seconds=900)
    _execute_b(h)
    assert h.bridge.on_price(110.0, ts=_et(15, 55)) is None
    exit_entry = h.bridge.tick_time_exit(_et(16, 0))
    assert exit_entry["time_exit"]["stale"] is False
    assert exit_entry["time_exit"]["price_age_seconds"] == 300.0
    h.close()


def test_path1_prior_session_position_is_not_the_schedulers_case(tmp_path):
    h = Harness(tmp_path)
    _execute_b(h)
    # Restart the NEXT morning: the position's deadline has passed,
    # so the startup pass owns it (recovery block raised) — the
    # scheduler must not close it, even ticking at that day's 16:00.
    b2 = _restart(h, now_fn=lambda: _et(10, 0, day=15))
    assert b2.status()["risk"]["automated_entries"] == \
        "BLOCKED — RECOVERY PENDING"
    assert b2.tick_time_exit(_et(16, 0, day=15)) is None
    assert b2.status()["paper"]["position"]["side"] == "LONG"
    assert b2.status()["paper"]["executions"][0]["status"] == "OPEN"
    h.close()


# ---------------------------------------------------------------------------
# Path 2a — deadline price recoverable (window injected by the test)
# ---------------------------------------------------------------------------

def test_path2a_recoverable_deadline_price(harness):
    rec = _execute_b(harness)
    # A price stamped inside the (test-injected) recovery window
    # [15:45, 16:00] is on the recorded tape before the restart.
    assert harness.bridge.on_price(112.0, ts=_et(15, 59)) is None
    # Restart completing at 16:20 ET, window W = 900 s injected.
    b2 = _restart(harness, recovery_window_seconds=900,
                  now_fn=lambda: _et(16, 20))
    # The startup pass detected the position, raised the block, then
    # closed it at the recorded window price as a recovered TIME_EXIT
    # and lifted the block — in that journal order.
    entries = b2.journal_entries()
    kinds = [e.get("action") for e in entries]
    assert _recovery_events(b2) == ["RAISED", "LIFTED"]
    exit_idx = next(i for i, e in enumerate(entries)
                    if e.get("exit_reason") == "TIME_EXIT")
    assert kinds.index("RECOVERY_BLOCK") < exit_idx
    status = b2.status()
    assert status["paper"]["position"]["side"] is None
    execution = status["paper"]["executions"][0]
    assert execution["status"] == "CLOSED"
    exit_entry = execution["exit"]
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["fill_price"] == 112.0
    assert exit_entry["exit_pnl"] == 16.0  # (112 - 104) x 1 x $2
    evidence = exit_entry["time_exit"]
    assert evidence["mechanism"] == "RESTART_RECOVERY"
    assert evidence["recovered"] is True
    assert evidence["deadline_et"] == _et(16, 0).isoformat()
    assert evidence["price_source_ts"] == _et(15, 59).isoformat()
    assert evidence["recovery_window_seconds"] == 900.0
    assert "late_exit_exception" not in exit_entry
    # Block lifted: the surface is clear and a fresh record is
    # evaluated on its merits.
    assert status["risk"]["automated_entries"] == "NOT BLOCKED"
    assert status["risk"]["recovery_block"] is None
    b2.set_automation_paused(False)
    fresh = copy.deepcopy(rec)
    fresh["signal_id"] = "fresh-after-recovery"
    res = b2.execute_record(fresh)
    assert res["status"] == "EXECUTED"


# ---------------------------------------------------------------------------
# Path 2b — deadline price NOT recoverable (the shipped default)
# ---------------------------------------------------------------------------

def test_path2b_late_exit_exception_shipped_default(harness):
    rec = _execute_b(harness)
    assert harness.bridge.on_price(108.0, ts=_et(14, 0)) is None
    # Restart at 16:20 ET with the window UNSET, as shipped: no price
    # can qualify as verifiable, so the pass raises the block and
    # waits for the first post-restart price.
    b2 = _restart(harness, now_fn=lambda: _et(16, 20))
    status = b2.status()
    assert status["paper"]["position"]["side"] == "LONG"
    assert status["risk"]["automated_entries"] == \
        "BLOCKED — RECOVERY PENDING"
    block = status["risk"]["recovery_block"]
    assert block["signal_id"] == rec["signal_id"]
    assert block["session_date"] == "2023-11-14"
    assert block["deadline_et"] == _et(16, 0).isoformat()
    assert _recovery_events(b2) == ["RAISED"]

    # While blocked, a new qualified B record is rejected with the
    # recovery-block reason and journaled.
    b2.set_automation_paused(False)
    second = copy.deepcopy(rec)
    second["signal_id"] = "second-during-recovery-block"
    res = b2.execute_record(second)
    assert res["status"] == "REJECTED"
    assert res["reason"] == pb.R_RECOVERY_BLOCK
    assert b2.status()["paper"]["position"]["qty"] == 1

    # The first post-restart price (between brackets) closes the
    # position — as LATE_EXIT_EXCEPTION, explicitly NOT TIME_EXIT,
    # with the full discrepancy journaled.
    exit_entry = b2.on_price(108.0, ts=_et(16, 25))
    assert exit_entry["exit_reason"] == pb.EXIT_LATE_EXCEPTION
    assert exit_entry["exit_reason"] != "TIME_EXIT"
    assert "time_exit" not in exit_entry
    assert exit_entry["fill_price"] == 108.0
    evidence = exit_entry["late_exit_exception"]
    assert evidence["mechanism"] == "RESTART_RECOVERY"
    assert evidence["recovered"] is False
    assert evidence["deadline_et"] == _et(16, 0).isoformat()
    assert evidence["actual_exit_ts_et"] == _et(16, 25).isoformat()
    assert evidence["lateness_seconds"] == 1500.0
    assert evidence["recovery_failure_reason"] == \
        "RECOVERY_WINDOW_NOT_SET"
    assert evidence["recovery_window"] == "NOT_SET"
    # The block lifts only after the closure.
    assert _recovery_events(b2) == ["RAISED", "LIFTED"]
    assert b2.status()["risk"]["automated_entries"] == "NOT BLOCKED"
    # The block rejection was state-dependent: re-presented now, the
    # same record is evaluated on its merits and executes.
    harness.reset_cooldown()
    res2 = b2.execute_record(second)
    assert res2["status"] == "EXECUTED"


def test_path2b_block_persists_until_a_price_arrives(harness):
    _execute_b(harness)
    b2 = _restart(harness, now_fn=lambda: _et(16, 40))
    # No price has been supplied since the restart: the position
    # cannot close and the block stays up — the design does not
    # pretend otherwise.
    assert b2.status()["risk"]["automated_entries"] == \
        "BLOCKED — RECOVERY PENDING"
    assert b2.status()["paper"]["executions"][0]["status"] == "OPEN"
    # A timestamp-less price is still a price: it closes the position
    # as LATE_EXIT_EXCEPTION, its exit instant read from the bridge
    # clock (the injected restart clock, 16:40 ET).
    exit_entry = b2.on_price(109.0)
    assert exit_entry["exit_reason"] == pb.EXIT_LATE_EXCEPTION
    evidence = exit_entry["late_exit_exception"]
    assert evidence["price_source_ts"] is None
    assert evidence["actual_exit_ts_et"] == _et(16, 40).isoformat()
    assert evidence["lateness_seconds"] == 2400.0
    assert b2.status()["risk"]["automated_entries"] == "NOT BLOCKED"


def test_path2b_window_injected_but_no_price_inside_it(harness):
    _execute_b(harness)
    # The only pre-restart tape price inside the session is stamped
    # 15:30 — outside the injected window [15:45, 16:00].
    assert harness.bridge.on_price(108.0, ts=_et(15, 30)) is None
    b2 = _restart(harness, recovery_window_seconds=900,
                  now_fn=lambda: _et(16, 20))
    assert b2.status()["risk"]["automated_entries"] == \
        "BLOCKED — RECOVERY PENDING"
    exit_entry = b2.on_price(108.0, ts=_et(16, 25))
    assert exit_entry["exit_reason"] == pb.EXIT_LATE_EXCEPTION
    evidence = exit_entry["late_exit_exception"]
    assert evidence["recovery_failure_reason"] == "NO_VERIFIABLE_PRICE"
    assert evidence["recovery_window"] == 900.0


# ---------------------------------------------------------------------------
# Path 2c — restart returns BEFORE the deadline
# ---------------------------------------------------------------------------

def test_path2c_restart_before_deadline_no_recovery_action(harness):
    _execute_b(harness)
    b2 = _restart(harness, now_fn=lambda: _et(15, 50))
    # The deadline has not passed: the recovery pass takes no action
    # — no block, no exit, nothing journaled by the pass.
    assert _recovery_events(b2) == []
    status = b2.status()
    assert status["risk"]["automated_entries"] == "NOT BLOCKED"
    assert status["risk"]["recovery_block"] is None
    assert status["paper"]["position"]["side"] == "LONG"
    # Mechanism 1 then fires normally at 16:00 ET.
    assert b2.on_price(110.0, ts=_et(15, 55)) is None
    assert b2.tick_time_exit(_et(15, 59)) is None
    exit_entry = b2.tick_time_exit(_et(16, 0))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["time_exit"]["mechanism"] == "SCHEDULED"
    assert exit_entry["time_exit"]["price_age_seconds"] == 300.0


# ---------------------------------------------------------------------------
# Cross-cutting: the blocked payload still validates; the evaluator
# never sees a post-restart position; server wiring is in place.
# ---------------------------------------------------------------------------

def test_blocked_status_payload_validates_fresh(harness, tmp_path):
    _execute_b(harness)
    b2 = _restart(harness, now_fn=lambda: _et(16, 20))
    payload = json.loads(json.dumps(b2.status()))
    assert payload["risk"]["automated_entries"] == \
        "BLOCKED — RECOVERY PENDING"
    panel = _load_module("pb_panel_for_time_exit",
                         "test_paper_bridge_panel.py")
    results = panel._run_validator(
        [{"name": "blocked", "payload": payload}], tmp_path)
    classification, rules = results["blocked"]
    assert classification == "fresh", rules
    assert rules == []


def test_server_wiring_scheduler_loop_and_price_delegation():
    # Source-level pins (the repo's established style for wiring that
    # only runs inside the deployed service loop): the scheduler loop
    # exists, is registered at startup, and the TradingView PRICE
    # handler presents prices to the bridge when one exists.
    src = (Path(__file__).resolve().parents[1] / "server.py").read_text()
    assert "async def paper_bridge_time_exit_loop" in src
    assert "_asyncio.create_task(paper_bridge_time_exit_loop())" in src
    assert "bridge.tick_time_exit" in src
    assert "_bridge.on_price, fp, alert_time" in src
    assert "_check_bracket_exits(fp)" in src  # the no-bridge path stays
