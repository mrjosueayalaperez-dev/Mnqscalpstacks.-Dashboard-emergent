"""Paper bridge — FINAL REVIEW ROUND (Nov 21, 2026).

Founder-authorized examination of the completion build, adopting
Zelator's five review items. This file pins Items A, B and D (Item C
— the scheduler loop in a running process — is proven by the
scripted subprocess run saved as evidence in
``~/workspace/phase2/docs/scheduler_loop_evidence.py`` / ``.log``;
Item E is a record distinction, stated in the round's report).

    Item A — stale-price execution: exactly what the scheduled exit
             does when the most recent supplied price is 10 s old,
             5 min old, 30 min old, stamped after the deadline, of
             unknowable age, or absent entirely. The 16:00 ET exit
             requirement is preserved — the exit fires — but the
             evidence must never present a recorded tape price as a
             verified current market price: every tape-priced exit
             now carries ``price_basis: "SUPPLIED_TAPE"``.
    Item B — timezone and session boundaries: ET conversion, DST
             transition days, weekends, a market holiday (the bridge
             has NO holiday calendar — a holiday is treated as a
             session day; pinned as the characterized behavior),
             prior sessions, and the 15:59:59 / 16:00:01 restart
             boundary.
    Item D — engine→bridge crash consistency: the engine books an
             execution and the process dies before the bridge
             mirrors it. Before this round the next startup silently
             erased the orphan. Now the startup consistency check
             detects the divergence, journals it as
             ENGINE_BRIDGE_INCONSISTENCY, and blocks new automated
             entries until it is resolved or founder-reviewed.

Everything runs on the acceptance suite's Harness — the real
pipeline, Analyst consumer, and Stage 2 engine; nothing is mocked.
Where a test needs a session date other than the fixture's
2023-11-14, it overrides the produced record's ``data_timestamp``
(deterministic test data, labeled as such) — the session date is
derived from that field by the bridge's own rule. The fixture
record's brackets are 85.0 (stop) / 130.0 (target), entry 104.0.
"""

import copy
import importlib.util
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:1")  # never contacted

import paper_bridge as pb  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
SESSION = (2023, 11, 14)  # the acceptance fixture's session date (ET)


def _et(hour, minute, second=0, day=SESSION[2], month=SESSION[1],
        year=SESSION[0]):
    return datetime(year, month, day, hour, minute, second, tzinfo=ET)


def _load_module(name, filename):
    path = Path(__file__).with_name(filename)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


acc = _load_module("pb_acceptance_for_final_review",
                   "test_paper_bridge_acceptance.py")
Harness = acc.Harness


@pytest.fixture()
def harness(tmp_path):
    h = Harness(tmp_path)
    yield h
    h.close()


def _restart(h, **bridge_kw):
    """Close the harness's bridge and construct a new one over the
    SAME journal DBs — the established restart pattern."""
    db_path = h.bridge.db_path
    store_path = str(h.dir / "signals.db")
    h.bridge.close()
    h.bridge = pb.PaperBridge(db_path=db_path,
                              signal_store_path=store_path,
                              **bridge_kw)
    return h.bridge


def _execute_b(h):
    out = h.b_record()
    h.bridge.set_automation_paused(False)
    res = h.bridge.execute_record(out["record"])
    assert res["status"] == "EXECUTED"
    return out["record"]


def _execute_b_on(h, data_timestamp_iso):
    """Execute the fixture record with its data_timestamp overridden
    so the bridge derives a different session date (deterministic
    test data; the record is otherwise the pipeline's own output)."""
    out = h.b_record()
    rec = copy.deepcopy(out["record"])
    rec["data_timestamp"] = data_timestamp_iso
    h.bridge.set_automation_paused(False)
    res = h.bridge.execute_record(rec)
    assert res["status"] == "EXECUTED", res
    return rec


def _recovery_events(bridge):
    return [e["bridge"]["recovery_block"]["event"]
            for e in bridge.journal_entries()
            if e.get("action") == "RECOVERY_BLOCK"]


# ---------------------------------------------------------------------------
# Item A — stale-price execution: the per-age table
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stamp,expected_age", [
    (_et(15, 59, 50), 10.0),    # 10 seconds old at the deadline
    (_et(15, 55), 300.0),       # 5 minutes old
    (_et(15, 30), 1800.0),      # 30 minutes old
])
def test_item_a_scheduled_exit_price_ages(harness, stamp, expected_age):
    _execute_b(harness)
    assert harness.bridge.on_price(110.0, ts=stamp) is None
    exit_entry = harness.bridge.tick_time_exit(_et(16, 0))
    # The exit requirement is preserved at every age: the exit fires.
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["fill_price"] == 110.0
    evidence = exit_entry["time_exit"]
    assert evidence["mechanism"] == "SCHEDULED"
    # The evidence is explicit about what the price IS: the bridge's
    # own recorded supplied price — never a live market quote.
    assert evidence["price_basis"] == "SUPPLIED_TAPE"
    assert evidence["price_source_ts"] == stamp.isoformat()
    assert evidence["price_age_seconds"] == expected_age
    # Gate 2A unset: age is a plain fact, no stale verdict exists.
    assert evidence["staleness_threshold"] == "NOT_SET"
    assert "stale" not in evidence
    assert "price_stamped_after_deadline" not in evidence


def test_item_a_fill_only_price_stamped_after_deadline(harness):
    # No price is ever supplied after execution: the only tape entry
    # is the position's own fill, whose source timestamp is the
    # record's data_timestamp — for this fixture 18:59 ET, AFTER the
    # 16:00 deadline. The computed age is therefore negative. It is
    # journaled as computed (never clamped into a plausible-looking
    # value) and explicitly flagged, so the exit price cannot be
    # mistaken for a price that existed at the deadline.
    rec = _execute_b(harness)
    exit_entry = harness.bridge.tick_time_exit(_et(16, 0))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    evidence = exit_entry["time_exit"]
    assert evidence["price_basis"] == "SUPPLIED_TAPE"
    deadline = _et(16, 0)
    expected_age = round(
        deadline.timestamp()
        - pb._to_et(rec["data_timestamp"]).timestamp(), 3)
    assert expected_age < 0  # the fixture's stamp is past the deadline
    assert evidence["price_age_seconds"] == expected_age
    assert evidence["price_stamped_after_deadline"] is True


def test_item_a_no_price_on_tape_miss_is_journaled(harness):
    _execute_b(harness)
    # Fault injection at the storage seam: the tape's rows are lost
    # (in the real flow the execution fill is taped, so an empty tape
    # with an open position means the tape itself was lost). Before
    # this round the scheduler returned None on every tick and the
    # deadline miss passed silently.
    harness.bridge._db.execute("DELETE FROM bridge_price_tape")
    harness.bridge._db.commit()
    assert harness.bridge.tick_time_exit(_et(16, 0)) is None
    misses = [e for e in harness.bridge.journal_entries()
              if e.get("action") == "SCHEDULED_EXIT_NO_PRICE"]
    assert len(misses) == 1
    miss = misses[0]["bridge"]
    assert miss["deadline_et"] == _et(16, 0).isoformat()
    assert miss["session_date"] == "2023-11-14"
    # No exit was booked — an exit cannot be booked without a price —
    # and the position remains open and visible.
    status = harness.bridge.status()
    assert status["paper"]["position"]["side"] == "LONG"
    assert status["paper"]["executions"][0]["status"] == "OPEN"
    # A later tick does not spam the journal with the same fact.
    assert harness.bridge.tick_time_exit(_et(16, 5)) is None
    misses = [e for e in harness.bridge.journal_entries()
              if e.get("action") == "SCHEDULED_EXIT_NO_PRICE"]
    assert len(misses) == 1
    # When a price finally arrives, the continuously-held position
    # closes through the evaluator route as before.
    exit_entry = harness.bridge.on_price(110.0, ts=_et(16, 10))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["time_exit"]["mechanism"] == "SUPPLIED_PRICE"
    assert harness.bridge.status()["paper"]["position"]["side"] is None


def test_item_a_timestamp_less_last_price_age_unknown(harness):
    _execute_b(harness)
    assert harness.bridge.on_price(110.0, ts=_et(15, 30)) is None
    # A later price supplied WITHOUT a timestamp is the most recent
    # supplied price; its age is unknowable and the evidence says so
    # (source and age are null) rather than inventing one.
    assert harness.bridge.on_price(111.0) is None
    exit_entry = harness.bridge.tick_time_exit(_et(16, 0))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["fill_price"] == 111.0
    evidence = exit_entry["time_exit"]
    assert evidence["price_basis"] == "SUPPLIED_TAPE"
    assert evidence["price_source_ts"] is None
    assert evidence["price_age_seconds"] is None


# ---------------------------------------------------------------------------
# Item B — timezone and session boundaries
# ---------------------------------------------------------------------------

def test_item_b_to_et_conversions():
    # UTC stamp → ET (EST, UTC−5 in November).
    assert pb._to_et("2023-11-14T21:00:00+00:00") == _et(16, 0)
    # A non-ET offset (+05:30) converts through UTC correctly.
    assert pb._to_et("2023-11-15T02:30:00+05:30") == _et(16, 0)
    # A naive stamp is read as UTC by the documented convention.
    assert pb._to_et("2023-11-14T21:00:00") == _et(16, 0)
    # The fall-back ambiguous hour: the two 01:30s are distinct
    # instants and convert distinctly (EDT −04:00, then EST −05:00).
    first = pb._to_et("2026-11-01T05:30:00+00:00")
    second = pb._to_et("2026-11-01T06:30:00+00:00")
    assert (first.hour, first.minute) == (1, 30)
    assert (second.hour, second.minute) == (1, 30)
    assert first.utcoffset().total_seconds() == -4 * 3600
    assert second.utcoffset().total_seconds() == -5 * 3600


def test_item_b_dst_spring_forward_deadline_is_wall_clock(harness):
    # Sunday Mar 8, 2026: clocks spring forward (EST → EDT). The
    # deadline is 16:00 ET WALL-CLOCK on the session date = 20:00Z.
    _execute_b_on(harness, "2026-03-08T14:00:00+00:00")  # 10:00 EDT
    assert harness.bridge.on_price(
        110.0, ts=datetime(2026, 3, 8, 19, 30, tzinfo=UTC)) is None
    # 19:59:59Z = 15:59:59 EDT: no fire.
    assert harness.bridge.tick_time_exit(
        datetime(2026, 3, 8, 19, 59, 59, tzinfo=UTC)) is None
    # 20:00:00Z = 16:00:00 EDT: fires.
    exit_entry = harness.bridge.tick_time_exit(
        datetime(2026, 3, 8, 20, 0, tzinfo=UTC))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["time_exit"]["session_date"] == "2026-03-08"
    assert exit_entry["time_exit"]["deadline_et"] == \
        datetime(2026, 3, 8, 16, 0, tzinfo=ET).isoformat()


def test_item_b_dst_fall_back_deadline_is_wall_clock(harness):
    # Sunday Nov 1, 2026: clocks fall back (EDT → EST). The deadline
    # is 16:00 ET WALL-CLOCK = 21:00Z that day (not 20:00Z).
    _execute_b_on(harness, "2026-11-01T14:00:00+00:00")  # 09:00 EST
    assert harness.bridge.on_price(
        110.0, ts=datetime(2026, 11, 1, 20, 30, tzinfo=UTC)) is None
    # 20:00Z = 15:00 EST: an hour early — no fire (a fixed UTC−4
    # reading would wrongly fire here).
    assert harness.bridge.tick_time_exit(
        datetime(2026, 11, 1, 20, 0, tzinfo=UTC)) is None
    # 20:59:59Z = 15:59:59 EST: no fire. 21:00Z = 16:00 EST: fires.
    assert harness.bridge.tick_time_exit(
        datetime(2026, 11, 1, 20, 59, 59, tzinfo=UTC)) is None
    exit_entry = harness.bridge.tick_time_exit(
        datetime(2026, 11, 1, 21, 0, tzinfo=UTC))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["time_exit"]["session_date"] == "2026-11-01"


def test_item_b_weekend_scheduler_stands_down_recovery_owns(harness):
    # Session date Friday Nov 17, 2023. The scheduler must not treat
    # Saturday as the position's session: a Saturday 16:00 tick is
    # not its case and closes nothing.
    _execute_b_on(harness, "2023-11-17T15:00:00+00:00")  # Fri 10:00 ET
    assert harness.bridge.on_price(110.0, ts=_et(15, 30, day=17)) is None
    assert harness.bridge.tick_time_exit(_et(16, 0, day=18)) is None
    assert harness.bridge.tick_time_exit(_et(16, 0, day=19)) is None
    assert harness.bridge.status()["paper"]["position"]["side"] == "LONG"
    # A position still open on the weekend is the startup recovery
    # pass's case: restart Saturday morning → block raised.
    b2 = _restart(harness, now_fn=lambda: _et(10, 0, day=18))
    assert _recovery_events(b2) == ["RAISED"]
    assert b2.status()["risk"]["automated_entries"] == \
        "BLOCKED — RECOVERY PENDING"


def test_item_b_market_holiday_treated_as_session_day(harness):
    # CHARACTERIZED LIMITATION, pinned as the actual behavior: the
    # bridge has no market-holiday calendar. Thanksgiving (Thu
    # Nov 26, 2026) is treated exactly like any other session day —
    # the scheduler fires at 16:00 ET. (Whether holidays should
    # suppress the exit is a founder decision, not an assumption
    # this round may bake in.)
    _execute_b_on(harness, "2026-11-26T15:00:00+00:00")  # 10:00 EST
    assert harness.bridge.on_price(
        110.0, ts=datetime(2026, 11, 26, 15, 30, tzinfo=ET)) is None
    exit_entry = harness.bridge.tick_time_exit(
        datetime(2026, 11, 26, 16, 0, tzinfo=ET))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["time_exit"]["session_date"] == "2026-11-26"


def test_item_b_prior_session_position_not_schedulers_case(harness):
    # Re-pin (also covered by the A1 specification file): a position
    # from yesterday is never closed by today's scheduler tick.
    _execute_b(harness)
    assert harness.bridge.on_price(110.0, ts=_et(15, 30)) is None
    assert harness.bridge.tick_time_exit(_et(16, 0, day=15)) is None
    assert harness.bridge.status()["paper"]["position"]["side"] == "LONG"


def test_item_b_restart_just_before_deadline_scheduler_owns(harness):
    _execute_b(harness)
    # Restart completing at 15:59:59 ET: the deadline has NOT passed,
    # so the recovery pass takes no action…
    b2 = _restart(harness, now_fn=lambda: _et(15, 59, 59))
    assert _recovery_events(b2) == []
    assert b2.status()["risk"]["automated_entries"] == "NOT BLOCKED"
    # …and Mechanism 1 owns the position when the deadline arrives.
    assert b2.on_price(110.0, ts=_et(15, 59, 59)) is None
    exit_entry = b2.tick_time_exit(_et(16, 0))
    assert exit_entry["exit_reason"] == "TIME_EXIT"
    assert exit_entry["time_exit"]["mechanism"] == "SCHEDULED"


def test_item_b_restart_just_after_deadline_recovery_owns(harness):
    _execute_b(harness)
    # Restart completing at 16:00:01 ET: the deadline HAS passed, so
    # the recovery pass owns the position from construction…
    b2 = _restart(harness, now_fn=lambda: _et(16, 0, 1))
    assert _recovery_events(b2) == ["RAISED"]
    assert b2.status()["risk"]["automated_entries"] == \
        "BLOCKED — RECOVERY PENDING"
    # …and the scheduler must not touch it, even at the deadline
    # instant itself.
    assert b2.tick_time_exit(_et(16, 0, 1)) is None
    assert b2.status()["paper"]["position"]["side"] == "LONG"


# ---------------------------------------------------------------------------
# Item D — engine→bridge crash consistency
# ---------------------------------------------------------------------------

def test_item_d_consistent_restart_no_false_positive(harness):
    _execute_b(harness)
    b2 = _restart(harness)
    inconsistencies = [e for e in b2.journal_entries()
                       if e.get("action")
                       == "ENGINE_BRIDGE_INCONSISTENCY"]
    assert inconsistencies == []
    status = b2.status()
    assert status["risk"]["consistency_block"] is None
    # The restart runs under the real clock, long past the fixture
    # position's 2023 deadline, so Mechanism 2's recovery block is
    # legitimately up — the point here is that the CONSISTENCY check
    # adds no block of its own on a consistent restart.
    assert status["risk"]["automated_entries"] == \
        "BLOCKED — RECOVERY PENDING"
    assert status["paper"]["position"]["side"] == "LONG"


def _crash_restart(h, patch_attr, patch_fn):
    """Execute through bridge1 with one mirror seam interrupted,
    then construct bridge2 over the same journal DB WITHOUT closing
    bridge1 — a process death has no close(). Returns (record, b2).
    The caller restores engine state via the close order in
    ``_cleanup_crash``."""
    out = h.b_record()
    rec = out["record"]
    h.bridge.set_automation_paused(False)
    original = getattr(pb.PaperBridge, patch_attr)
    setattr(pb.PaperBridge, patch_attr, patch_fn(original))
    try:
        with pytest.raises(RuntimeError):
            h.bridge.execute_record(rec)
    finally:
        setattr(pb.PaperBridge, patch_attr, original)
    # The engine booked the position; the bridge has no open row.
    assert h.bridge.server._operator_state["position"]["side"] == "LONG"
    assert h.bridge.open_execution() is None
    b2 = pb.PaperBridge(db_path=h.bridge.db_path,
                        signal_store_path=str(h.dir / "signals.db"))
    h.bridge2 = b2
    return rec, b2


def _cleanup_crash(h):
    # bridge2.close() restores ITS snapshot (the orphan state);
    # bridge1.close() then restores the pristine pre-execution
    # state — the order returns the shared engine module to exactly
    # what the harness found. The fixture teardown closes bridge1
    # once more (a no-op restore) and the store.
    if getattr(h, "bridge2", None) is not None:
        h.bridge2.close()
        h.bridge2 = None
    h.bridge.close()


def test_item_d_crash_at_row_save_detected_journaled_blocked(harness):
    def interrupt(original):
        def boom(self, row):
            if row.get("status") == "OPEN":
                raise RuntimeError("simulated process death at the"
                                   " execution-row save")
            return original(self, row)
        return boom

    rec, b2 = _crash_restart(harness, "_save_execution", interrupt)
    try:
        # Detected and journaled as an explicit inconsistency fact,
        # on BOTH surfaces: the EXECUTION journal entry has no
        # execution row, and the engine position found at startup
        # is accounted for by no journal execution.
        entries = [e for e in b2.journal_entries()
                   if e.get("action") == "ENGINE_BRIDGE_INCONSISTENCY"]
        assert len(entries) == 1
        types = {d["type"]
                 for d in entries[0]["bridge"]["divergences"]}
        assert types == {
            "EXECUTION_JOURNAL_WITHOUT_EXECUTION_ROW",
            "ENGINE_POSITION_NOT_IN_BRIDGE_JOURNAL",
        }
        # The orphan is NOT silently rehydrated (it was never in the
        # journal) and NOT double-executed: the surface shows flat,
        # the block is up, and a fresh record is rejected with the
        # consistency reason.
        status = b2.status()
        assert status["paper"]["position"]["side"] is None
        assert status["risk"]["consistency_block"] is not None
        assert status["risk"]["automated_entries"] == \
            "BLOCKED — INCONSISTENCY UNRESOLVED"
        b2.set_automation_paused(False)
        harness.reset_cooldown()
        fresh = copy.deepcopy(rec)
        fresh["signal_id"] = "fresh-during-inconsistency-block"
        res = b2.execute_record(fresh)
        assert res["status"] == "REJECTED"
        assert res["reason"] == pb.R_CONSISTENCY_BLOCK
    finally:
        _cleanup_crash(harness)


def test_item_d_crash_before_journal_write_detected(harness):
    def interrupt(original):
        def boom(self, kind, entry):
            if kind == "EXECUTION":
                raise RuntimeError("simulated process death before"
                                   " the mirror journal write")
            return original(self, kind, entry)
        return boom

    rec, b2 = _crash_restart(harness, "_journal", interrupt)
    try:
        # The bridge journal holds no trace of the execution at all;
        # only the engine-position surface can see the divergence —
        # and it does.
        entries = [e for e in b2.journal_entries()
                   if e.get("action") == "ENGINE_BRIDGE_INCONSISTENCY"]
        assert len(entries) == 1
        types = {d["type"]
                 for d in entries[0]["bridge"]["divergences"]}
        assert types == {"ENGINE_POSITION_NOT_IN_BRIDGE_JOURNAL"}
        divergence = entries[0]["bridge"]["divergences"][0]
        assert divergence["engine_position"]["side"] == "LONG"
        assert divergence["engine_position"]["qty"] == 1
        assert b2.status()["risk"]["automated_entries"] == \
            "BLOCKED — INCONSISTENCY UNRESOLVED"
    finally:
        _cleanup_crash(harness)
