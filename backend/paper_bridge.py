"""Paper bridge — the operational join between the signal pipeline, the
Command Analyst, and the Stage 2 paper engine.

Phase 2 built three components that each stop, deliberately, at their own
boundary:

- ``signal_pipeline.SignalPipeline`` validates events, evaluates Strategy A
  (alert-reported Six Gates) and Strategy B (unmodified Bot B), and journals
  canonical signal records. It creates NO orders — that firewall is a
  property of the pipeline and this module does not weaken it: the bridge
  is a separate, explicit *consumer* of journaled records.
- ``app.analyst_signals.review_signal`` (Command Dashboard tree)
  deterministically reviews a canonical record and returns a disposition.
  It has no execution authority and never reclassifies.
- Stage 2's paper engine (``server._execute_order`` and its safety chain)
  executes simulated orders against the operator state and journals them
  in the operator journal schema (phase ``SIM_LOG_ONLY``).

This bridge is the missing consumer that carries ONE canonical record
through the full chain:

    canonical record → Analyst review → risk validation →
    Stage 2 simulated execution → bridge journal

Hard rules (founder directive, Nov 20, 2026 — paper-trading readiness):

- Only records the strategy layer qualified may proceed: Strategy B
  ``qualification_status == "qualified"``; Strategy A
  ``qualification_status == "qualified_alert_reported"`` (A's qualified
  state per its own alert-reported model). Direction must be LONG/SHORT.
- Only Analyst dispositions CONSISTENT or QUALIFIED_WITH_CONCERNS may
  proceed. CONTRADICTION_DETECTED / INSUFFICIENT_DATA are execution
  rejections, journaled with the review attached.
- Risk validation enforces Stage 2's own bounds — the automation gate
  (``automation_paused`` defaults True = blocked; the bridge treats it as
  a hard gate for its AUTO-origin executions, stricter than the engine's
  manual-order path), the kill switch, ``MAX_ORDER_QTY``,
  ``MAX_BRACKET_TICKS`` — plus the PAPER PROFILES below.
- STRATEGY B PAPER PROFILE (founder-approved parameters, Nov 21, 2026 —
  the ONLY auto-execution profile): automation scope is Strategy B
  only. ``PAPER_PROFILE_QTY = 1`` MNQ; the stop is the record's own
  structural stop, used exactly as recorded and never widened; the
  target is the opposite 15-minute range boundary taken from the
  record's own range fields (``market_state.range_high`` /
  ``range_low``) — never invented, and for Strategy B the bridge never
  falls back to a derived R target; a record lacking the range data
  its exit framework needs is REJECTED with ``EXIT_FRAMEWORK_MISSING``.
  Planned risk = stop ticks × $0.50 (MNQ tick value at qty 1) +
  estimated fees/slippage must be ≤ $200.00, else the setup is
  REJECTED with ``RISK_CAP_EXCEEDED`` and journaled with the full
  planned-risk breakdown. The 16:00 ET session-close rule is carried
  by THREE routes under the Amendment A1 labeling rule (below): the
  supplied-price evaluator (a B position still open when a supplied
  price update is stamped ≥ 16:00 ET on the position's session date
  closes at that update's price, ``TIME_EXIT``), the scheduled exit,
  and restart recovery.
- AMENDMENT A1 TIME EXIT (founder-authorized Nov 21, 2026 — the
  Render readiness package's design correction, implemented here):
  two mechanisms. MECHANISM 1 — a clock-driven scheduler
  (:class:`TimeExitScheduler`, driven by ``tick(now)``) fires at
  16:00 ET on an open B position's session date and closes it at the
  most recent price supplied to the bridge, ``TIME_EXIT`` with
  ``mechanism: "SCHEDULED"``; a prior-session position is never the
  scheduler's case. MECHANISM 2 — a startup recovery pass runs after
  rehydration and before any new automated entry is accepted: an
  open B position whose session deadline has passed blocks new
  automated entries (journaled ``RECOVERY_BLOCK``, state-dependent)
  until it is closed — at a verifiable deadline-window price from
  the bridge's own recorded price tape (``TIME_EXIT``,
  ``recovered: true``) or, when no such price qualifies, at the
  first available price under the distinct reason
  ``LATE_EXIT_EXCEPTION`` with the full discrepancy journaled.
  LABELING RULE: ``TIME_EXIT`` is used only by Mechanism 1, by a
  qualified recovery, and by the supplied-price evaluator for a
  position this process has held continuously (never for a
  post-restart closure — a rehydrated past-deadline position is
  owned by recovery, and its closures route through it). The two
  outcomes carry distinct evidence keys (``time_exit`` vs
  ``late_exit_exception``).
- GATE 2A PARAMETERS ARE NOT DECIDED (founder/Zelator decision
  outstanding): the price-staleness threshold (P-A1-1) and the
  recovery window width (P-A1-2) are constructor parameters whose
  shipped default is UNSET (``None``). With the threshold unset, a
  scheduled exit journals the price age as a plain fact and records
  ``staleness_threshold: "NOT_SET"`` — no stale/not-stale verdict.
  With the window unset, NO recorded price qualifies as a verifiable
  deadline price, so recovery always takes the
  ``LATE_EXIT_EXCEPTION`` path (``recovery_failure_reason =
  "RECOVERY_WINDOW_NOT_SET"``). Tests may inject values to prove the
  parameterized branches; an injected value is a test fixture, never
  a product default.
- FINAL REVIEW ROUND (Nov 21, 2026) — evidence and consistency
  corrections, no doctrine or Gate 2A change: (1) every tape-priced
  exit evidence block now carries ``price_basis: "SUPPLIED_TAPE"`` —
  an explicit marker that the price is the bridge's own recorded
  supplied price, not a live market quote; a scheduled-exit price
  stamped after the deadline (negative computed age) is flagged
  ``price_stamped_after_deadline`` and its age journaled as
  computed, never clamped. (2) A scheduled exit that reaches the
  deadline with NO price on the tape books no exit — an exit cannot
  be booked without a price — and journals the miss once per process
  as ``SCHEDULED_EXIT_NO_PRICE``; the position remains open and
  visible. (3) A startup consistency check compares the engine's
  state with the bridge journal (execution entries without rows,
  engine positions no journal execution accounts for, journal
  positions that did not rehydrate); any divergence is journaled as
  ``ENGINE_BRIDGE_INCONSISTENCY`` and blocks new automated entries
  for the life of the bridge — detected and recorded, never silently
  absorbed, never silently double-executed.
- STRATEGY A IS ATTENDED-ONLY (founder decision, Nov 21, 2026): an A
  record that qualifies and passes the Analyst gate is reviewed and
  journaled as ``HELD_ATTENDED_ONLY`` — the bridge never auto-executes
  it, whatever the automation state. (The legacy 1R target derivation
  is retained in code for the generic path only; no record reaches it
  under the current scope: B uses its structural target, A is held.)
  Canonical records still never carry ``risk.target`` — the contract
  forbids target / quantity / exposure while risk is UNAPPROVED — so
  every target above is a bridge-side profile parameter, disclosed as
  such in every journal entry, not a strategy rule smuggled into a
  record.
- ``risk_approval_status`` remains ``UNAPPROVED`` in every record,
  decision, and journal entry this module produces. The paper profile
  parameters are test-scoped defaults pending the founder's dollar-risk
  decisions for Strategy A and Strategy B.
- Idempotency: a ``signal_id`` can produce at most one execution. A
  repeat of an EXECUTED signal returns the existing execution record and
  is journaled as a duplicate — never a second position. A repeat of a
  signal rejected for a *deterministic* reason (not qualified, Analyst
  contradiction, missing/invalid exit framework, risk bound) likewise
  returns the existing rejection: the same record cannot evaluate
  differently. A signal rejected only for a *state-dependent* reason
  (automation paused, kill switch, a position already open, an engine
  cooldown) may be re-presented after the state changes and is then
  re-evaluated; every attempt, including the original rejection, stays
  in the journal. Since automation is paused by default, the alternative
  — state rejections being permanent — would kill every signal that
  arrives before the operator's first resume.
- Every outcome — executed, rejected (paused, contradiction, missing
  exits, bounds, duplicate, position already open, not qualified) — is
  journaled with the signal_id, the full canonical record, the Analyst
  review, and the risk decision, so any simulated trade is reproducible
  from its recorded inputs.
- Simulated fills are marked ``fill_price_source = "SIMULATED"`` (the
  tape is set from the record's own price through the same
  ``market_feed.set_live_price`` seam the TradingView PRICE action uses)
  and are never presented as market prices.
- The Stage 2 engine holds ONE position. The bridge therefore allows at
  most one open bridge position at a time and rejects further qualified
  signals with ``POSITION_ALREADY_OPEN`` rather than merging two
  strategies into one book. (Characterized engine limitation; see the
  readiness report §C.)

Local journal: Stage 2's operator journal is Mongo-backed
(``db.operator_orders`` via motor) and no MongoDB runs in this local
environment — Stage 2's own test suite substitutes mongomock for the
same reason. The bridge therefore (a) drives the real engine with a
mongomock-backed ``server.db`` for in-process operation, and (b) mirrors
every journal entry into a durable local SQLite journal in the SAME
operator-journal schema (extended with a ``bridge`` block), which is the
local system of record that makes restart/replay persistence possible.
In a deployed setting with a real Mongo, ``server.db`` is unchanged and
the engine's own journal is primary; the bridge mirror remains the
chain-level audit trail.

Analyst consumer loading: ``app/analyst_signals.py`` is self-contained
(no imports beyond ``__future__``), so the bridge loads it directly by
file path from the Phase 2 Command clone — no vendored copy that could
diverge, no sys.path pollution. Override with ``MQ_COMMAND_TREE``.
"""

from __future__ import annotations

import asyncio
import copy
import importlib.util
import json
import os
import sqlite3
import threading
import uuid
from datetime import date as dt_date, datetime, time as dt_time, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from zoneinfo import ZoneInfo

import signal_contract as sc

# ---------------------------------------------------------------------------
# Paper profile — SIMULATION PARAMETERS, not a risk approval.
# ---------------------------------------------------------------------------

#: Contracts per simulated execution under the paper profile.
PAPER_PROFILE_QTY = 1
#: Target derivation: 1R, where R is the record's own structural stop
#: distance. A profile parameter of the simulator — not a strategy rule.
PAPER_PROFILE_TARGET_R = 1.0
#: MNQ tick size in points (Stage 2 bracket math uses the same 0.25).
TICK_POINTS = 0.25

# ---------------------------------------------------------------------------
# Founder-approved Strategy B paper profile (founder decision,
# Nov 21, 2026). These are approved PAPER-trading parameters — the
# profile under which this bridge may auto-execute Strategy B records
# in simulation. They authorize no live execution of any kind.
# ---------------------------------------------------------------------------

#: Maximum planned risk per Strategy B paper trade, in dollars,
#: INCLUDING the estimated fees and slippage below.
B_PAPER_RISK_CAP_DOLLARS = 200.00
#: MNQ tick value at quantity 1: $2.00 per point / 4 ticks per point
#: (the same $2-per-point figure Stage 2's _pnl_for_close uses).
B_PAPER_TICK_DOLLARS = 0.50
#: ESTIMATE — round-trip commissions/fees allowance for one MNQ
#: contract in the paper profile. An estimate for planning-risk
#: arithmetic only; the Stage 2 engine's fill model books zero fees.
B_PAPER_EST_FEES_RT_DOLLARS = 4.00
#: ESTIMATE — slippage allowance for the paper profile, in ticks
#: (1 tick of entry slippage + 1 tick of exit slippage).
B_PAPER_EST_SLIPPAGE_TICKS = 2
#: The slippage allowance in dollars: 2 ticks × $0.50 = $1.00.
B_PAPER_EST_SLIPPAGE_DOLLARS = B_PAPER_EST_SLIPPAGE_TICKS * B_PAPER_TICK_DOLLARS
#: Time exit: a Strategy B position still open at 4:00 PM ET on its
#: session date closes under the Amendment A1 mechanisms (module
#: docstring): the supplied-price evaluator, the clock-driven
#: scheduler (Mechanism 1), or startup recovery (Mechanism 2). This
#: bridge reads no live feed; its tape is the prices supplied to it.
B_PAPER_TIME_EXIT_ET = dt_time(16, 0)
#: Session-date and deadline arithmetic is done in exchange-local time.
ET_ZONE = ZoneInfo("America/New_York")


def strategy_b_paper_profile_block() -> Dict[str, Any]:
    """The founder-approved Strategy B paper profile as a plain block
    for journal entries and the status surface — stated as paper
    parameters, never as execution authority."""
    return {
        "profile": "STRATEGY_B_PAPER",
        "qty": PAPER_PROFILE_QTY,
        "risk_cap_dollars": B_PAPER_RISK_CAP_DOLLARS,
        "tick_value_dollars": B_PAPER_TICK_DOLLARS,
        "est_fees_round_trip_dollars": B_PAPER_EST_FEES_RT_DOLLARS,
        "est_slippage_ticks": B_PAPER_EST_SLIPPAGE_TICKS,
        "est_slippage_dollars": B_PAPER_EST_SLIPPAGE_DOLLARS,
        "target_rule": "opposite 15-minute range boundary, taken from"
                       " the record's own range fields",
        "stop_rule": "the record's structural stop, used exactly as"
                     " recorded; never widened to fit the cap",
        "over_cap_rule": "reject and journal (RISK_CAP_EXCEEDED)",
        "time_exit": "16:00 ET on the position's session date"
                     " — scheduled exit (Amendment A1 Mechanism 1);"
                     " restart recovery labels an unrecoverable"
                     " deadline exit LATE_EXIT_EXCEPTION"
                     " (Mechanism 2)",
    }


def _b_planned_risk(stop_ticks: int) -> Dict[str, Any]:
    """Planned-risk breakdown for one Strategy B paper trade:
    stop_ticks × $0.50 (tick value, qty 1) + $4.00 estimated
    round-trip fees + $1.00 estimated slippage (2 ticks), against
    the $200.00 founder-approved cap. All figures are dollars."""
    stop_dollars = round(stop_ticks * B_PAPER_TICK_DOLLARS, 2)
    total = round(stop_dollars + B_PAPER_EST_FEES_RT_DOLLARS
                  + B_PAPER_EST_SLIPPAGE_DOLLARS, 2)
    return {
        "stop_ticks": stop_ticks,
        "stop_dollars": stop_dollars,
        "est_fees": B_PAPER_EST_FEES_RT_DOLLARS,
        "est_slippage": B_PAPER_EST_SLIPPAGE_DOLLARS,
        "total": total,
        "cap_dollars": B_PAPER_RISK_CAP_DOLLARS,
        "within_cap": total <= B_PAPER_RISK_CAP_DOLLARS,
    }


def _to_et(ts) -> Optional[datetime]:
    """Normalize a supplied timestamp to an aware America/New_York
    datetime. Accepts a datetime or an ISO-8601 string; a naive value
    is read as UTC. Returns None for anything unparseable."""
    if isinstance(ts, str):
        try:
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            return None
    if not isinstance(ts, datetime):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(ET_ZONE)

#: Explanation source label — verbatim, never paraphrased.
PROVIDER_LABEL = sc.EXPLANATION_SOURCE_FALLBACK  # DETERMINISTIC_FALLBACK — PROVIDER_NOT_CONNECTED

#: Analyst dispositions that may proceed to risk validation/execution.
PROCEEDING_DISPOSITIONS = ("CONSISTENT", "QUALIFIED_WITH_CONCERNS")

#: qualification_status values that count as "qualified" per strategy.
QUALIFIED_STATUS = {
    sc.STRATEGY_B: "qualified",
    sc.STRATEGY_A: "qualified_alert_reported",
}

# Rejection reason codes (journaled verbatim).
R_NOT_QUALIFIED = "NOT_QUALIFIED"
R_ANALYST_BLOCKED = "ANALYST_BLOCKED"
R_AUTOMATION_PAUSED = "AUTOMATION_PAUSED"
R_KILL_SWITCH = "KILL_SWITCH_ACTIVE"
R_POSITION_OPEN = "POSITION_ALREADY_OPEN"
R_EXIT_MISSING = "EXIT_FRAMEWORK_MISSING"
R_EXIT_INVALID = "EXIT_FRAMEWORK_INVALID"
R_RISK_BOUND = "RISK_BOUND_EXCEEDED"
R_RISK_CAP = "RISK_CAP_EXCEEDED"
R_HELD_ATTENDED = "HELD_ATTENDED_ONLY"
R_ENGINE_BLOCKED = "ENGINE_BLOCKED"
R_JOURNAL_FAILED = "JOURNAL_FAILED"
#: Amendment A1 Mechanism 2: new automated entries are blocked while
#: a past-deadline Strategy B position awaits its recovery exit.
R_RECOVERY_BLOCK = "RECOVERY_BLOCK"
#: Final review round (Nov 21, 2026): the startup consistency check
#: found the Stage 2 engine's state and the bridge journal disagree
#: (Item D) — new automated entries are blocked until the divergence
#: is resolved or founder-reviewed.
R_CONSISTENCY_BLOCK = "ENGINE_BRIDGE_INCONSISTENCY"

#: Exit reason for a post-deadline closure that is NOT a Mechanism 1
#: scheduled exit and NOT a qualified deadline-window recovery
#: (Amendment A1 labeling rule). Never interchangeable with TIME_EXIT.
EXIT_LATE_EXCEPTION = "LATE_EXIT_EXCEPTION"

#: Rejection reasons that depend on operator/engine STATE at presentation
#: time rather than on the record's content. A signal rejected only for
#: one of these may be re-evaluated when re-presented after the state
#: changes; every other rejection is final for that signal_id.
STATE_DEPENDENT_REASONS = frozenset({
    R_AUTOMATION_PAUSED, R_KILL_SWITCH, R_POSITION_OPEN, R_ENGINE_BLOCKED,
    R_RECOVERY_BLOCK, R_CONSISTENCY_BLOCK,
})


def default_bridge_db_path() -> str:
    env = os.environ.get("PAPER_BRIDGE_DB")
    if env:
        return env
    return os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "data", "paper_bridge.db")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(coro):
    """Run a coroutine from synchronous bridge code."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    # Called from within a running loop (not expected for bridge use):
    # run on a dedicated thread so asyncio.run is legal.
    import threading

    box: Dict[str, Any] = {}

    def _target():
        try:
            box["value"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001 - re-raised below
            box["error"] = exc

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


# ---------------------------------------------------------------------------
# Analyst consumer (Command tree, loaded by file path — no vendored copy)
# ---------------------------------------------------------------------------

def _default_command_tree() -> Path:
    env = os.environ.get("MQ_COMMAND_TREE")
    if env:
        return Path(env)
    # This file: ~/workspace/phase2/dashboard/gh-clone/backend/paper_bridge.py
    # Command clone: ~/workspace/phase2/command-dashboard/gh-clone
    return Path(__file__).resolve().parents[3] / "command-dashboard" / "gh-clone"


def load_analyst_signals(command_tree: Optional[os.PathLike] = None):
    """Load ``app/analyst_signals.py`` from the Phase 2 Command clone."""
    tree = Path(command_tree) if command_tree else _default_command_tree()
    path = tree / "app" / "analyst_signals.py"
    if not path.is_file():
        raise FileNotFoundError(f"Analyst consumer not found at {path}")
    spec = importlib.util.spec_from_file_location("mq_analyst_signals", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Stage 2 engine access (dashboard tree's server.py, imported lazily)
# ---------------------------------------------------------------------------

_PRISTINE_OPERATOR_STATE: Dict[str, Any] = {
    "connection": {"broker": "NinjaTrader", "status": "DISCONNECTED",
                   "account": "Sim101"},
    "balance": 100000.00,
    "daily_pnl": 0.0,
    "daily_trades": 0,
    "max_daily_loss": -100.00,
    "max_daily_trades": 20,
    "session_started_at": "2026-11-16T00:00:00+00:00",
    "automation_paused": True,   # Stage 2 default: OFF until founder enables
    "kill_switch": False,
    "last_order_at": 0.0,
    "journal_failures": 0,
    "persistence_ok": True,
    "position": {"side": None, "qty": 0, "avg_entry": 0.0,
                 "unrealized_pnl": 0.0, "sl_price": None, "tp_price": None},
}


def _load_server():
    """Import the dashboard backend's server module (Stage 2 engine).

    Mirrors Stage 2's own offline test arrangement: a placeholder
    MONGO_URL is set if unset (the motor client is lazy; the bridge
    rebinds ``server.db`` to a local mongomock database before use).
    """
    os.environ.setdefault("MONGO_URL", "mongodb://localhost:1")
    import server  # noqa: WPS433 (deliberate lazy import)

    return server


# ---------------------------------------------------------------------------
# Amendment A1 Mechanism 1 — the scheduled-exit component
# ---------------------------------------------------------------------------

class TimeExitScheduler:
    """Clock-driven scheduler for the Strategy B 16:00 ET time exit.

    Deliberately a thin, deterministic component: the service loop
    calls :meth:`tick` periodically (the deployed wiring lives in
    server.py's loop set), and tests call it with an injected
    instant. ``tick(now)`` evaluates Mechanism 1 exactly once for
    ``now`` (a datetime or ISO-8601 string; default: the bridge's
    clock) and returns the mirrored exit entry if the scheduled exit
    fired, else None. All state and journaling live in the bridge;
    this class holds no state of its own beyond the bridge reference,
    so it cannot double-fire across callers — a fired exit closes
    the position, and a later tick finds no open position."""

    def __init__(self, bridge: "PaperBridge"):
        self._bridge = bridge

    def tick(self, now=None) -> Optional[Dict[str, Any]]:
        bridge = self._bridge
        now_et = _to_et(now) if now is not None else bridge._now_et()
        if now_et is None:
            return None
        with bridge._lock:
            return bridge._scheduled_exit_locked(now_et)


# ---------------------------------------------------------------------------
# The bridge
# ---------------------------------------------------------------------------

class PaperBridge:
    """Carries canonical signal records through review → risk → the
    Stage 2 paper engine, journaling every outcome.

    One bridge owns the Stage 2 operator state for its session: the
    prior module state is snapshotted on init and restored on
    :meth:`close`. On init, an open position recorded in the bridge
    journal is rehydrated into the engine state, so a restart over the
    same journal DB preserves positions and idempotency.
    """

    def __init__(
        self,
        db_path: Optional[str] = None,
        *,
        command_tree: Optional[os.PathLike] = None,
        signal_store_path: Optional[str] = None,
        analyst_module=None,
        server_module=None,
        staleness_threshold_seconds: Optional[float] = None,
        recovery_window_seconds: Optional[float] = None,
        now_fn: Optional[Callable[[], datetime]] = None,
    ):
        # Gate 2A parameters (Amendment A1 §A1.5) — PROPOSED values,
        # NOT decided. Both ship UNSET (None): no staleness verdict is
        # ever journaled, and no recorded price qualifies as a
        # verifiable deadline price for recovery. A caller (in
        # practice, a test) may inject a value to exercise the
        # parameterized branch; injection is not adoption.
        self._staleness_threshold_seconds = staleness_threshold_seconds
        self._recovery_window_seconds = recovery_window_seconds
        # Clock seam for the startup recovery pass (the pipeline's
        # now_fn pattern): returns the startup instant; tests drive
        # simulated restart times through it.
        self._now_fn = now_fn or (lambda: datetime.now(ET_ZONE))
        #: Amendment A1 Mechanism 2 state: while not None, an open
        #: past-deadline Strategy B position is unrecovered and new
        #: automated entries are blocked. Set by the startup pass.
        self._recovery_block: Optional[Dict[str, Any]] = None
        #: Final review round, Item D: while not None, the startup
        #: consistency check found the engine's state and the bridge
        #: journal in disagreement; new automated entries are blocked
        #: until the divergence is resolved or founder-reviewed.
        self._consistency_block: Optional[Dict[str, Any]] = None
        #: Final review round, Item A: (signal_id, session_date) pairs
        #: whose scheduled-exit no-price miss this process has already
        #: journaled — the fact is recorded once per process, not on
        #: every scheduler tick.
        self._no_price_miss_journaled: set = set()
        self.db_path = db_path or default_bridge_db_path()
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False (finding DR-26): the status endpoint
        # is served from a FastAPI threadpool thread, not the thread
        # that constructed the bridge; sqlite3 connections are
        # thread-affine by default and raised ProgrammingError there.
        # All journal/execution access is serialized through this lock.
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.db_path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._init_schema()

        self.analyst = analyst_module or load_analyst_signals(command_tree)
        self._signal_store_path = signal_store_path  # for status(); optional

        # --- bind the Stage 2 engine for local operation ----------------
        self.server = server_module or _load_server()
        srv = self.server
        self._saved_state = copy.deepcopy(srv._operator_state)
        self._saved_db = srv.db
        self._saved_discord = getattr(srv, "send_discord_signal", None)

        from mongomock_motor import AsyncMongoMockClient

        srv.db = AsyncMongoMockClient()["paper_bridge_local"]

        async def _no_discord(*args, **kwargs):
            return None

        srv.send_discord_signal = _no_discord

        # Fresh operator session in the engine's own default shape, then
        # rehydrate any open bridge position from the durable journal.
        srv._operator_state.clear()
        srv._operator_state.update(copy.deepcopy(_PRISTINE_OPERATOR_STATE))
        self._rehydrate()

        # Amendment A1: the scheduled-exit component (Mechanism 1)
        # and the startup recovery pass (Mechanism 2) — the pass runs
        # after rehydration and before any new automated entry can be
        # accepted (construction precedes every execute_record call).
        self.time_exit_scheduler = TimeExitScheduler(self)
        self._startup_recovery()
        # Final review round, Item D: with the engine bound and the
        # journal rehydrated, verify the two records of the system's
        # state agree — before any new automated entry is accepted.
        self._startup_consistency_check()

    # -- durable journal --------------------------------------------------

    def _init_schema(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS bridge_journal (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                signal_id TEXT,
                kind TEXT NOT NULL,
                entry TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_bridge_journal_signal
                ON bridge_journal(signal_id);
            CREATE TABLE IF NOT EXISTS bridge_executions (
                signal_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,        -- OPEN | CLOSED | REJECTED
                strategy_id TEXT,
                record TEXT NOT NULL,        -- full canonical record
                review TEXT,                 -- Analyst review (or null)
                risk_decision TEXT,          -- risk validation outcome
                order_entry TEXT,            -- operator-journal entry
                exit_entry TEXT,             -- bracket-exit entry, if any
                reason TEXT,                 -- rejection reason code
                created_ts TEXT NOT NULL,
                updated_ts TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bridge_price_tape (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                price REAL NOT NULL,
                -- The price's own source timestamp (epoch + ISO), as
                -- supplied with the price; NULL when the price was
                -- supplied without one. Recorded durably so the
                -- Amendment A1 recovery search survives a restart:
                -- a deadline price is verifiable only from this tape.
                source_epoch REAL,
                source_ts TEXT,
                recorded_ts TEXT NOT NULL
            );
            """
        )
        self._db.commit()

    def _journal(self, kind: str, entry: Dict[str, Any]) -> Dict[str, Any]:
        self._db.execute(
            "INSERT INTO bridge_journal (ts, signal_id, kind, entry)"
            " VALUES (?, ?, ?, ?)",
            (entry.get("ts") or _now_iso(),
             (entry.get("bridge") or {}).get("signal_id")
             or (entry.get("source_alert") or {}).get("signal_id"),
             kind, json.dumps(entry)),
        )
        self._db.commit()
        return entry

    def journal_entries(self) -> list:
        with self._lock:
            rows = self._db.execute(
                "SELECT entry FROM bridge_journal ORDER BY seq").fetchall()
            return [json.loads(r["entry"]) for r in rows]

    def _get_execution(self, signal_id: str) -> Optional[Dict[str, Any]]:
        row = self._db.execute(
            "SELECT * FROM bridge_executions WHERE signal_id = ?",
            (signal_id,)).fetchone()
        if row is None:
            return None
        out = dict(row)
        for field in ("record", "review", "risk_decision", "order_entry",
                      "exit_entry"):
            out[field] = json.loads(out[field]) if out[field] else None
        return out

    def _save_execution(self, exec_row: Dict[str, Any]) -> None:
        now = _now_iso()
        self._db.execute(
            "INSERT INTO bridge_executions (signal_id, status, strategy_id,"
            " record, review, risk_decision, order_entry, exit_entry,"
            " reason, created_ts, updated_ts)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
            " ON CONFLICT(signal_id) DO UPDATE SET status=excluded.status,"
            " review=excluded.review, risk_decision=excluded.risk_decision,"
            " order_entry=excluded.order_entry,"
            " exit_entry=excluded.exit_entry, reason=excluded.reason,"
            " updated_ts=excluded.updated_ts",
            (exec_row["signal_id"], exec_row["status"],
             exec_row.get("strategy_id"),
             json.dumps(exec_row["record"]),
             json.dumps(exec_row["review"]) if exec_row.get("review") else None,
             json.dumps(exec_row["risk_decision"])
             if exec_row.get("risk_decision") else None,
             json.dumps(exec_row["order_entry"])
             if exec_row.get("order_entry") else None,
             json.dumps(exec_row["exit_entry"])
             if exec_row.get("exit_entry") else None,
             exec_row.get("reason"),
             exec_row.get("created_ts") or now, now),
        )
        self._db.commit()

    def _rehydrate(self) -> None:
        """Restore the engine position from the durable journal after a
        restart: the latest OPEN execution's resulting position and the
        journal's last daily P&L. Idempotency needs no rehydration — it
        lives in the bridge_executions primary key."""
        srv = self.server
        row = self._db.execute(
            "SELECT order_entry FROM bridge_executions WHERE status = 'OPEN'"
            " ORDER BY created_ts DESC LIMIT 1").fetchone()
        if row is not None and row["order_entry"]:
            entry = json.loads(row["order_entry"])
            pos = entry.get("resulting_position")
            if pos:
                srv._operator_state["position"] = copy.deepcopy(pos)
        last = self._db.execute(
            "SELECT entry FROM bridge_journal ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        if last is not None:
            entry = json.loads(last["entry"])
            if isinstance(entry.get("daily_pnl"), (int, float)):
                srv._operator_state["daily_pnl"] = entry["daily_pnl"]
        count = self._db.execute(
            "SELECT COUNT(*) AS n FROM bridge_executions"
            " WHERE status IN ('OPEN', 'CLOSED')").fetchone()
        srv._operator_state["daily_trades"] = int(count["n"])

    # -- recorded price tape (Amendment A1) ------------------------------

    def _now_et(self) -> datetime:
        """The bridge's current instant in ET, via the clock seam."""
        et = _to_et(self._now_fn())
        return et if et is not None else datetime.now(ET_ZONE)

    def _record_tape(self, price: float,
                     source_et: Optional[datetime]) -> None:
        """Record one supplied price on the durable tape. The tape is
        the bridge's own price history: the scheduler's exit price and
        the recovery pass's verifiable-price search both read it, and
        because it lives in the journal DB it survives a restart."""
        self._db.execute(
            "INSERT INTO bridge_price_tape"
            " (price, source_epoch, source_ts, recorded_ts)"
            " VALUES (?, ?, ?, ?)",
            (float(price),
             source_et.timestamp() if source_et is not None else None,
             source_et.isoformat() if source_et is not None else None,
             _now_iso()))
        self._db.commit()

    def _last_tape(self) -> Optional[Dict[str, Any]]:
        row = self._db.execute(
            "SELECT price, source_epoch, source_ts FROM bridge_price_tape"
            " ORDER BY seq DESC LIMIT 1").fetchone()
        return dict(row) if row is not None else None

    def _deadline_window_price(self, deadline: datetime
                               ) -> Optional[Dict[str, Any]]:
        """The latest tape price whose SOURCE timestamp falls inside
        the recovery window [deadline − W, deadline] — a verifiable
        deadline price (Amendment A1 §A1.3.2a: recorded by this bridge,
        with its source timestamp, in the durable journal).

        Gate 2A: W (P-A1-2) ships UNSET — with no window adopted, NO
        price qualifies, and this returns None unconditionally."""
        window = self._recovery_window_seconds
        if window is None:
            return None
        hi = deadline.timestamp()
        row = self._db.execute(
            "SELECT price, source_epoch, source_ts FROM bridge_price_tape"
            " WHERE source_epoch IS NOT NULL"
            " AND source_epoch >= ? AND source_epoch <= ?"
            " ORDER BY source_epoch DESC, seq DESC LIMIT 1",
            (hi - float(window), hi)).fetchone()
        return dict(row) if row is not None else None

    # -- operator controls (mirror Stage 2's control surface semantics) ---

    def set_automation_paused(self, paused: bool) -> None:
        """Explicit operator action, mirroring POST /operator/control/
        {pause|resume}. Default state is paused; unpausing is always an
        explicit act, never a side effect of processing a signal."""
        self.server._operator_state["automation_paused"] = bool(paused)

    @property
    def automation_paused(self) -> bool:
        return bool(self.server._operator_state["automation_paused"])

    def open_execution(self) -> Optional[Dict[str, Any]]:
        row = self._db.execute(
            "SELECT * FROM bridge_executions WHERE status = 'OPEN'"
            " ORDER BY created_ts DESC LIMIT 1").fetchone()
        if row is None:
            return None
        return self._get_execution(row["signal_id"])

    # -- journal entry construction (operator-journal schema + bridge) ----

    def _paper_profile_block(self, record):
        """The paper-profile block stamped into a journal entry's
        bridge section: the founder-approved Strategy B profile for B
        records; the generic simulation-parameters note otherwise."""
        if (record or {}).get("strategy_id") == sc.STRATEGY_B:
            return strategy_b_paper_profile_block()
        return {
            "qty": PAPER_PROFILE_QTY,
            "target_r": PAPER_PROFILE_TARGET_R,
            "note": "SIMULATION PARAMETERS — test-scoped defaults"
                    " pending the founder's dollar-risk decisions;"
                    " not a risk approval.",
        }

    def _base_entry(self, record, review, risk_decision, action, **kw):
        entry = {
            "id": str(uuid.uuid4()),
            "ts": _now_iso(),
            "action": action,
            "symbol": (record or {}).get("instrument") or "MNQ",
            "qty": kw.get("qty"),
            "order_type": kw.get("order_type"),
            "limit_price": None,
            "fill_price": kw.get("fill_price"),
            "fill_price_source": kw.get("fill_price_source"),
            "sl_ticks": kw.get("sl_ticks"),
            "tp_ticks": kw.get("tp_ticks"),
            "preset": kw.get("preset"),
            "sl_price": kw.get("sl_price"),
            "tp_price": kw.get("tp_price"),
            "resulting_position": copy.deepcopy(
                self.server._operator_state["position"]),
            "daily_pnl": self.server._operator_state["daily_pnl"],
            "phase": "SIM_LOG_ONLY",
            "origin": "PAPER_BRIDGE",
            "source_alert": {"signal_id": (record or {}).get("signal_id"),
                             "strategy_id": (record or {}).get("strategy_id")},
            "bridge": {
                "signal_id": (record or {}).get("signal_id"),
                "strategy_id": (record or {}).get("strategy_id"),
                "strategy_version": (record or {}).get("strategy_version"),
                "analyst_disposition": (review or {}).get("disposition"),
                "explanation_source": PROVIDER_LABEL,
                "risk_decision": risk_decision,
                "risk_approval_status": sc.RISK_UNAPPROVED,
                "paper_profile": self._paper_profile_block(record),
                "reason": kw.get("reason"),
            },
        }
        return entry

    def _reject(self, record, review, risk_decision, reason, detail=None):
        risk_decision = dict(risk_decision or {})
        risk_decision.update({"outcome": "REJECTED", "reason": reason,
                              "detail": detail,
                              "risk_approval_status": sc.RISK_UNAPPROVED})
        entry = self._base_entry(record, review, risk_decision, "REJECTED",
                                 reason=reason)
        self._journal("REJECTION", entry)
        self._save_execution({
            "signal_id": record.get("signal_id"), "status": "REJECTED",
            "strategy_id": record.get("strategy_id"),
            "record": record, "review": review,
            "risk_decision": risk_decision, "order_entry": entry,
            "exit_entry": None, "reason": reason,
        })
        return {"status": "REJECTED", "reason": reason, "detail": detail,
                "signal_id": record.get("signal_id"), "review": review,
                "risk_decision": risk_decision, "journal_entry": entry}

    def _hold_attended(self, record, review):
        """Strategy A attended-only hold (founder decision, Nov 21,
        2026): the record qualified and passed the Analyst gate, so it
        is journaled with its review — but the bridge never
        auto-executes a Strategy A record, whatever the automation
        state. The hold is deterministic (a property of the strategy,
        not of operator state), so a re-presented A record returns the
        existing hold as a duplicate."""
        detail = ("Strategy A is attended-only under the founder's"
                  " Nov 21, 2026 decision: the bridge reviews and"
                  " journals A records but never auto-executes them;"
                  " any execution is the founder's attended act,"
                  " outside this bridge.")
        risk_decision = {
            "outcome": "HELD",
            "reason": R_HELD_ATTENDED,
            "detail": detail,
            "risk_approval_status": sc.RISK_UNAPPROVED,
        }
        entry = self._base_entry(record, review, risk_decision,
                                 "HELD_ATTENDED_ONLY",
                                 reason=R_HELD_ATTENDED)
        self._journal("HELD", entry)
        self._save_execution({
            "signal_id": record.get("signal_id"), "status": "HELD",
            "strategy_id": record.get("strategy_id"),
            "record": record, "review": review,
            "risk_decision": risk_decision, "order_entry": entry,
            "exit_entry": None, "reason": R_HELD_ATTENDED,
        })
        return {"status": "HELD", "reason": R_HELD_ATTENDED,
                "detail": detail,
                "signal_id": record.get("signal_id"), "review": review,
                "risk_decision": risk_decision, "journal_entry": entry}

    # -- the chain ----------------------------------------------------------

    def execute_record(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Carry one canonical signal record through the full chain.

        Returns an outcome dict; every outcome is journaled. Never raises
        for a business-rule rejection; raises only for a record so
        malformed it carries no signal_id (nothing to journal against).
        """
        if not isinstance(record, dict) or not record.get("signal_id"):
            raise ValueError("record carries no signal_id; nothing to"
                             " journal against")
        with self._lock:
            return self._execute_record_locked(record)

    def _execute_record_locked(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record = copy.deepcopy(record)
        signal_id = record["signal_id"]

        # 1) Idempotency: a signal_id produces at most one execution.
        #    Executions and deterministic rejections are final; a
        #    state-dependent rejection falls through to re-evaluation
        #    (the earlier rejection remains in the journal).
        existing = self._get_execution(signal_id)
        if existing is not None and (
                existing["status"] in ("OPEN", "CLOSED")
                or existing.get("reason") not in STATE_DEPENDENT_REASONS):
            entry = self._base_entry(
                record, existing.get("review"),
                existing.get("risk_decision"), "DUPLICATE_SIGNAL",
                reason="DUPLICATE")
            self._journal("DUPLICATE", entry)
            return {"status": "DUPLICATE", "signal_id": signal_id,
                    "execution": existing, "journal_entry": entry}

        # 2) Qualification gate — per each strategy's own logic.
        cls = record.get("classification") or {}
        q_status = cls.get("qualification_status")
        direction = cls.get("classification")
        expected = QUALIFIED_STATUS.get(record.get("strategy_id"))
        if expected is None or q_status != expected or direction not in (
                "LONG", "SHORT"):
            return self._reject(
                record, None, {"outcome": "NOT_EVALUATED"},
                R_NOT_QUALIFIED,
                detail=(f"qualification_status={q_status!r},"
                        f" classification={direction!r}; this bridge only"
                        f" executes records qualified under their own"
                        f" strategy's logic (expected {expected!r} for"
                        f" {record.get('strategy_id')!r})"))

        # 3) Analyst review — the record is reviewed exactly as emitted.
        review = self.analyst.review_signal(copy.deepcopy(record))
        if review.get("disposition") not in PROCEEDING_DISPOSITIONS:
            return self._reject(
                record, review, {"outcome": "NOT_EVALUATED"},
                R_ANALYST_BLOCKED,
                detail=(f"Analyst disposition"
                        f" {review.get('disposition')!r}; contradictions:"
                        f" {review.get('contradictions')}; missing:"
                        f" {review.get('missing_fields')}"))

        # 3b) Strategy A is attended-only (founder decision, Nov 21,
        #     2026): it has qualified and passed the Analyst gate, so
        #     it is journaled — as a hold, never an auto-execution.
        if record.get("strategy_id") == sc.STRATEGY_A:
            return self._hold_attended(record, review)

        # 4) Risk validation — Stage 2 bounds + the paper profile.
        state = self.server._operator_state
        risk: Dict[str, Any] = {
            "paper_profile_qty": PAPER_PROFILE_QTY,
            "max_order_qty": self.server.MAX_ORDER_QTY,
            "max_bracket_ticks": self.server.MAX_BRACKET_TICKS,
            "risk_approval_status": sc.RISK_UNAPPROVED,
        }
        is_b = record.get("strategy_id") == sc.STRATEGY_B
        if is_b:
            risk["strategy_b_paper_profile"] = \
                strategy_b_paper_profile_block()
            # Best-effort planned-risk computation (pure arithmetic on
            # the record's own fields, no decision taken here) so that
            # even a state-gate rejection of a B record journals the
            # breakdown. The authoritative computation — and the cap
            # decision — happens at step 4b below, once the stop has
            # been validated.
            _risk_in = record.get("risk") or {}
            _entry_peek = _risk_in.get("proposed_entry")
            if not isinstance(_entry_peek, (int, float)) \
                    or isinstance(_entry_peek, bool):
                _entry_peek = (record.get("market_state") or {}).get("price")
            _stop_peek = _risk_in.get("structural_stop")
            if isinstance(_entry_peek, (int, float)) \
                    and not isinstance(_entry_peek, bool) \
                    and isinstance(_stop_peek, (int, float)) \
                    and not isinstance(_stop_peek, bool) \
                    and abs(_entry_peek - _stop_peek) > 0:
                risk["planned_risk"] = _b_planned_risk(
                    int(round(abs(_entry_peek - _stop_peek)
                              / TICK_POINTS)))
        if is_b and self._recovery_block is not None:
            # Amendment A1 Mechanism 2: a past-deadline Strategy B
            # position is unrecovered; new automated entries stay
            # blocked until its recovery exit closes it. The block is
            # state-dependent — the same record may be re-presented
            # after recovery completes and is then re-evaluated.
            return self._reject(
                record, review, risk, R_RECOVERY_BLOCK,
                detail=("a Strategy B position from session"
                        f" {self._recovery_block['session_date']} is"
                        " past its 16:00 ET deadline and has not been"
                        " closed by restart recovery; new automated"
                        " entries stay blocked until it closes"
                        " (Amendment A1 Mechanism 2)"))
        if is_b and self._consistency_block is not None:
            # Final review round, Item D: the startup consistency
            # check found the engine's state and the bridge journal
            # in disagreement. Entries stay blocked for the life of
            # this bridge — the divergence is resolved or
            # founder-reviewed, never silently absorbed. The block
            # is state-dependent: a later bridge over corrected
            # records re-evaluates on merits.
            return self._reject(
                record, review, risk, R_CONSISTENCY_BLOCK,
                detail=("the startup consistency check found the"
                        " Stage 2 engine's state and the bridge"
                        " journal in disagreement (journaled as"
                        " ENGINE_BRIDGE_INCONSISTENCY); new automated"
                        " entries stay blocked until the divergence"
                        " is resolved or founder-reviewed"))
        if state["kill_switch"]:
            return self._reject(record, review, risk, R_KILL_SWITCH)
        if state["automation_paused"]:
            return self._reject(
                record, review, risk, R_AUTOMATION_PAUSED,
                detail="automation_paused is True (Stage 2 default); an"
                       " explicit operator resume is required before any"
                       " simulated execution")
        if self.open_execution() is not None:
            return self._reject(
                record, review, risk, R_POSITION_OPEN,
                detail="the Stage 2 engine holds a single position; a"
                       " second strategy position is never merged into"
                       " the same book")

        risk_in = record.get("risk") or {}
        market = record.get("market_state") or {}
        entry_ref = risk_in.get("proposed_entry")
        if not isinstance(entry_ref, (int, float)):
            entry_ref = market.get("price")
        stop = risk_in.get("structural_stop")
        if not isinstance(stop, (int, float)) or isinstance(stop, bool):
            return self._reject(
                record, review, risk, R_EXIT_MISSING,
                detail="record carries no structural stop; without it"
                       " no planned risk can be computed and no bracket"
                       " can be set — the bridge never invents exits")
        if not isinstance(entry_ref, (int, float)) or isinstance(
                entry_ref, bool):
            return self._reject(
                record, review, risk, R_EXIT_INVALID,
                detail="record carries no numeric entry reference price")
        stop_distance = abs(entry_ref - stop)
        if stop_distance <= 0 or (direction == "LONG" and stop >= entry_ref) \
                or (direction == "SHORT" and stop <= entry_ref):
            return self._reject(
                record, review, risk, R_EXIT_INVALID,
                detail=(f"structural stop {stop} is not beyond the entry"
                        f" reference {entry_ref} for a {direction}"))
        stop_ticks = int(round(stop_distance / TICK_POINTS))
        risk.update({
            "entry_reference": entry_ref, "structural_stop": stop,
            "stop_distance_points": stop_distance,
            "stop_ticks": stop_ticks,
        })
        if is_b:
            # 4b) Founder-approved Strategy B profile (Nov 21, 2026).
            #     Target: the opposite 15-minute range boundary, from
            #     the record's OWN range fields — for a LONG the range
            #     high, for a SHORT the range low. If the record lacks
            #     the range data, the exit framework is incomplete:
            #     reject; never invent a target, and never fall back
            #     to a derived R target for Strategy B.
            target = market.get("range_high") if direction == "LONG" \
                else market.get("range_low")
            if not isinstance(target, (int, float)) \
                    or isinstance(target, bool) \
                    or (direction == "LONG" and target <= entry_ref) \
                    or (direction == "SHORT" and target >= entry_ref):
                return self._reject(
                    record, review, risk, R_EXIT_MISSING,
                    detail=(f"Strategy B record lacks the range data"
                            f" its founder-approved exit framework"
                            f" needs: market_state.range_high="
                            f"{market.get('range_high')!r},"
                            f" range_low={market.get('range_low')!r}"
                            f" for a {direction} from {entry_ref}; the"
                            f" target must be the opposite range"
                            f" boundary taken from the record itself —"
                            f" the bridge never invents a target and"
                            f" never falls back to a derived R target"
                            f" for Strategy B"))
            target_ticks = int(round(abs(target - entry_ref)
                                     / TICK_POINTS))
            planned = _b_planned_risk(stop_ticks)
            risk.update({
                "target_ticks": target_ticks,
                "target": target,
                "target_derivation": "opposite 15-minute range boundary"
                                     " from the record's own range"
                                     " fields (founder-approved"
                                     " Strategy B paper profile,"
                                     " Nov 21, 2026)",
                "planned_risk": planned,
            })
            if planned["total"] > B_PAPER_RISK_CAP_DOLLARS:
                return self._reject(
                    record, review, risk, R_RISK_CAP,
                    detail=(f"planned risk ${planned['total']:.2f}"
                            f" exceeds the founder-approved Strategy B"
                            f" paper cap of"
                            f" ${B_PAPER_RISK_CAP_DOLLARS:.2f} (stop"
                            f" ${planned['stop_dollars']:.2f} + est."
                            f" fees ${planned['est_fees']:.2f} + est."
                            f" slippage ${planned['est_slippage']:.2f});"
                            f" the setup is rejected and journaled,"
                            f" never resized — the stop is used exactly"
                            f" as recorded"))
        else:
            # Generic path (legacy paper profile): target derived at
            # 1R from the record's own structural stop. Under the
            # current founder scope no record reaches this branch —
            # Strategy B uses its structural target above and Strategy
            # A is held at step 3b — it is retained unchanged as the
            # guard for any future founder-authorized profile.
            target_ticks = int(round(
                stop_distance * PAPER_PROFILE_TARGET_R / TICK_POINTS))
            risk.update({
                "target_ticks": target_ticks,
                "target_derivation": f"{PAPER_PROFILE_TARGET_R}R from"
                                     " the record's own structural"
                                     " stop (paper-profile parameter)",
            })
        if PAPER_PROFILE_QTY > self.server.MAX_ORDER_QTY:
            return self._reject(record, review, risk, R_RISK_BOUND,
                                detail="paper profile qty exceeds"
                                       " MAX_ORDER_QTY")
        if stop_ticks > self.server.MAX_BRACKET_TICKS or \
                target_ticks > self.server.MAX_BRACKET_TICKS:
            return self._reject(
                record, review, risk, R_RISK_BOUND,
                detail=(f"bracket {max(stop_ticks, target_ticks)} ticks"
                        f" exceeds Stage 2 ceiling"
                        f" MAX_BRACKET_TICKS={self.server.MAX_BRACKET_TICKS}"))

        # 5) Simulated execution through the real Stage 2 engine. The
        # tape is set from the record's own price via the same feed seam
        # the TradingView PRICE action uses; the fill is therefore the
        # record's price, marked SIMULATED in the journal.
        srv = self.server
        srv.market_feed_set_live_price(float(entry_ref))
        # The fill price is a price supplied to the bridge: record it
        # on the durable tape (source: the record's own data
        # timestamp) so the scheduler and the recovery pass read one
        # history.
        self._record_tape(float(entry_ref),
                          _to_et(record.get("data_timestamp")))
        order = srv.OperatorOrder(
            action="BUY" if direction == "LONG" else "SELL",
            symbol="MNQ", qty=PAPER_PROFILE_QTY, order_type="MARKET",
            sl_ticks=stop_ticks, tp_ticks=target_ticks,
            preset="STRATEGY_B_PAPER_PROFILE" if is_b
            else "PAPER_PROFILE_1R")
        try:
            result = _run(srv._execute_order(
                order, origin="AUTO",
                source_alert={"signal_id": signal_id,
                              "strategy_id": record.get("strategy_id"),
                              "source": "paper_bridge"}))
        except Exception as exc:  # engine safety chain raised (HTTPException)
            detail = getattr(exc, "detail", None) or str(exc)
            return self._reject(record, review, risk, R_ENGINE_BLOCKED,
                                detail=f"Stage 2 safety chain: {detail}")
        order_entry = copy.deepcopy(result["order"])
        order_entry["fill_price_source"] = "SIMULATED"
        order_entry["origin"] = "PAPER_BRIDGE"
        order_entry["source_alert"] = {
            "signal_id": signal_id,
            "strategy_id": record.get("strategy_id"),
            "source": "paper_bridge"}
        risk["outcome"] = "EXECUTED" if result.get("journal_ok") else \
            "EXECUTED_JOURNAL_FAILED"
        order_entry["bridge"] = {
            "signal_id": signal_id,
            "strategy_id": record.get("strategy_id"),
            "strategy_version": record.get("strategy_version"),
            "analyst_disposition": review.get("disposition"),
            "explanation_source": PROVIDER_LABEL,
            "risk_decision": risk,
            "risk_approval_status": sc.RISK_UNAPPROVED,
            "paper_profile": self._paper_profile_block(record),
            "reason": None,
        }
        self._journal("EXECUTION", order_entry)
        self._save_execution({
            "signal_id": signal_id, "status": "OPEN",
            "strategy_id": record.get("strategy_id"),
            "record": record, "review": review, "risk_decision": risk,
            "order_entry": order_entry, "exit_entry": None,
            "reason": None,
        })
        if not result.get("journal_ok"):
            # Stage 2 finding-3 semantics: never a clean success when
            # the journal failed; the engine has already halted
            # automation. Surface it as its own outcome.
            return {"status": "EXECUTED_JOURNAL_FAILED",
                    "reason": R_JOURNAL_FAILED, "signal_id": signal_id,
                    "review": review, "risk_decision": risk,
                    "order": order_entry}
        return {"status": "EXECUTED", "signal_id": signal_id,
                "review": review, "risk_decision": risk,
                "order": order_entry}

    # -- position lifecycle -------------------------------------------------

    def on_price(self, price: float, ts=None) -> Optional[Dict[str, Any]]:
        """Drive the Stage 2 bracket-exit engine with a tape price.

        Returns the mirrored exit entry if an exit fired, else None.
        A bracket exit fills at the bracket price (Stage 2's stated
        fill model), marked SIMULATED. ``ts`` is the price update's
        timestamp (datetime or ISO-8601 string; naive read as UTC):
        when supplied, the founder-approved Strategy B time exit is
        also evaluated — a B position still open on an update stamped
        at or after 16:00 ET on its session date closes at that
        update's price with exit reason TIME_EXIT. Without ``ts`` no
        time evaluation is possible and none is attempted.

        Amendment A1 routing: every supplied price is first recorded
        on the durable tape. While a restart-recovery block is active
        (Mechanism 2), a price that does not fire a bracket exit
        routes through recovery resolution — never through the plain
        evaluator — so a post-restart closure is labeled TIME_EXIT
        only when a verifiable deadline-window price qualifies, and
        LATE_EXIT_EXCEPTION otherwise. A ``ts`` that is supplied but
        unparseable is journaled as a PRICE_TIME_GAP (visible, never
        silent) and the price is then treated as timestamp-less.
        """
        srv = self.server
        srv.market_feed_set_live_price(float(price))
        with self._lock:
            return self._on_price_locked(price, ts)

    def _on_price_locked(self, price: float, ts=None) -> Optional[Dict[str, Any]]:
        srv = self.server
        price = float(price)
        update_et = _to_et(ts) if ts is not None else None
        if ts is not None and update_et is None:
            self._journal_price_time_gap(ts)
        self._record_tape(price, update_et)
        exit_entry = _run(srv._check_bracket_exits(price))
        if not exit_entry:
            # Bracket levels get first claim on the update (a crossed
            # bracket fills at its own price under the engine's fill
            # model); the time rules apply to a position STILL OPEN
            # after the update's bracket evaluation.
            if self._recovery_block is not None:
                exit_entry = self._recovery_resolve_locked(
                    price, update_et)
            else:
                exit_entry = self._time_exit_locked(price, ts)
            if not exit_entry:
                return None
        return self._mirror_exit_locked(exit_entry)

    def _mirror_exit_locked(self, exit_entry: Dict[str, Any]
                            ) -> Dict[str, Any]:
        """Mirror an engine-booked exit into the bridge journal and
        mark the open execution CLOSED. If the closure resolves a
        restart-recovery block, the block lifts here — the single
        place every exit route (bracket, evaluator, scheduler,
        recovery) passes through."""
        exit_entry = copy.deepcopy(exit_entry)
        exit_entry["fill_price_source"] = "SIMULATED"
        exit_entry["origin"] = "PAPER_BRIDGE"
        open_exec = self.open_execution()
        if open_exec is not None:
            exit_entry["bridge"] = {
                "signal_id": open_exec["signal_id"],
                "strategy_id": open_exec.get("strategy_id"),
                "explanation_source": PROVIDER_LABEL,
                "risk_approval_status": sc.RISK_UNAPPROVED,
                "reason": exit_entry.get("exit_reason"),
            }
            exit_entry["source_alert"] = {
                "signal_id": open_exec["signal_id"],
                "strategy_id": open_exec.get("strategy_id"),
                "source": "paper_bridge"}
            self._journal("EXIT", exit_entry)
            open_exec["status"] = "CLOSED"
            open_exec["exit_entry"] = exit_entry
            self._save_execution(open_exec)
        if self._recovery_block is not None \
                and self.open_execution() is None:
            self._lift_recovery_block()
        return exit_entry

    def _journal_price_time_gap(self, raw_ts) -> None:
        """A supplied-but-unparseable price timestamp, journaled
        visibly (readiness package §5.2: the gap is part of the
        record, never silent). The price itself is still recorded on
        the tape, without a source timestamp."""
        open_exec = self.open_execution()
        entry = {
            "id": str(uuid.uuid4()),
            "ts": _now_iso(),
            "action": "PRICE_TIME_UNPARSEABLE",
            "symbol": "MNQ",
            "phase": "SIM_LOG_ONLY",
            "origin": "PAPER_BRIDGE",
            "bridge": {
                "signal_id": (open_exec or {}).get("signal_id"),
                "strategy_id": (open_exec or {}).get("strategy_id"),
                "raw_ts": str(raw_ts)[:120],
                "note": "a price update carried a timestamp that"
                        " could not be parsed; the price was"
                        " recorded on the tape without a source"
                        " timestamp and no time evaluation was"
                        " attempted for it",
                "risk_approval_status": sc.RISK_UNAPPROVED,
            },
        }
        self._journal("PRICE_TIME_GAP", entry)

    def _session_date_et(self, exec_row) -> Optional[dt_date]:
        """The open position's session date in America/New_York,
        derived from its record's data timestamp (falling back to the
        execution's creation time)."""
        record = exec_row.get("record") or {}
        for stamp in (record.get("data_timestamp"),
                      exec_row.get("created_ts")):
            et = _to_et(stamp) if stamp else None
            if et is not None:
                return et.date()
        return None

    def _book_close_locked(self, price: float, exit_reason: str,
                           evidence_key: str, evidence: Dict[str, Any]
                           ) -> Dict[str, Any]:
        """Close the engine's open position AT ``price`` under
        ``exit_reason``, booked through the engine's own
        P&L/journal/persist helpers in the same operator-journal
        shape as a bracket exit, with the caller's evidence block
        attached under ``evidence_key`` (``time_exit`` or
        ``late_exit_exception`` — the Amendment A1 labeling rule keeps
        the two keys, and the two reasons, distinct). Returns the
        booked entry, NOT yet mirrored into the bridge journal —
        callers pass it through :meth:`_mirror_exit_locked`."""
        srv = self.server

        async def _close_async():
            p = srv._operator_state["position"]
            pnl = srv._pnl_for_close(p["side"], p["avg_entry"],
                                     float(price), p["qty"])
            srv._operator_state["daily_pnl"] = round(
                srv._operator_state["daily_pnl"] + pnl, 2)
            entry = {
                "id": str(uuid.uuid4()),
                "ts": _now_iso(),
                "action": f"EXIT_{p['side']}",
                "symbol": "MNQ",
                "qty": p["qty"],
                "order_type": exit_reason,
                "limit_price": None,
                "fill_price": float(price),
                "exit_reason": exit_reason,
                "exit_pnl": round(pnl, 2),
                "resulting_position": srv._flat_position(),
                "daily_pnl": srv._operator_state["daily_pnl"],
                "phase": "SIM_LOG_ONLY",
                "origin": "ENGINE",
                "source_alert": None,
                evidence_key: evidence,
            }
            srv._operator_state["position"] = srv._flat_position()
            await srv._journal_operator(entry)
            await srv._persist_operator_state()
            return entry

        return _run(_close_async())

    def _open_b_position_locked(self):
        """(open execution, engine position) when a Strategy B
        position is genuinely open, else (None, None)."""
        open_exec = self.open_execution()
        if open_exec is None \
                or open_exec.get("strategy_id") != sc.STRATEGY_B:
            return None, None
        pos = self.server._operator_state["position"]
        if not pos.get("side") or not pos.get("qty"):
            return None, None
        return open_exec, pos

    def _time_exit_locked(self, price: float, ts) -> Optional[Dict[str, Any]]:
        """Founder-approved Strategy B time exit (Nov 21, 2026) —
        the supplied-price evaluator route.

        If the open position is a Strategy B position and the supplied
        price update is stamped at or after 16:00 ET on the position's
        session date, close the position AT THE UPDATE'S PRICE and
        return the exit entry (exit reason TIME_EXIT). Strategy A
        positions are unaffected (the B profile is B-only; in any
        case the bridge never holds an A position — A records are
        held, not executed). Returns None when the rule does not fire.

        Labeling (Amendment A1): this route is reached only for a
        position this process has held continuously — while a
        restart-recovery block is active, ``_on_price_locked`` routes
        through recovery resolution instead, so no post-restart
        closure is ever labeled here. The evidence carries
        ``mechanism: "SUPPLIED_PRICE"`` so the three TIME_EXIT routes
        (this evaluator, the scheduler, a qualified recovery) are
        distinguishable in the journal.
        """
        if ts is None:
            return None
        open_exec, _pos = self._open_b_position_locked()
        if open_exec is None:
            return None
        update_et = _to_et(ts)
        session_date = self._session_date_et(open_exec)
        if update_et is None or session_date is None:
            return None
        deadline = datetime.combine(session_date, B_PAPER_TIME_EXIT_ET,
                                      tzinfo=ET_ZONE)
        if update_et < deadline:
            return None
        evidence = {
            "rule": "16:00 ET on the position's session date"
                    " (founder-approved Strategy B paper"
                    " profile, Nov 21, 2026)",
            "mechanism": "SUPPLIED_PRICE",
            "session_date": session_date.isoformat(),
            "deadline_et": deadline.isoformat(),
            "update_ts_et": update_et.isoformat(),
            "price_basis": "SUPPLIED_TAPE",
            "fill_basis": "the supplied update price; the"
                          " bridge reads no market feed",
        }
        return self._book_close_locked(price, "TIME_EXIT",
                                       "time_exit", evidence)

    # -- Amendment A1 Mechanism 1: the scheduled 16:00 ET exit -----------

    def _scheduled_exit_locked(self, now_et: datetime
                               ) -> Optional[Dict[str, Any]]:
        """Mechanism 1 (Amendment A1 §A1.3.1): on a scheduler tick at
        or past 16:00 ET on the open B position's OWN session date,
        close it at the most recent price supplied to the bridge.

        A prior-session position is never this mechanism's case (it
        belongs to the startup recovery pass), and while a recovery
        block is active the scheduler does not touch the position.
        Bracket exits keep priority: the engine's bracket check runs
        first at the most recent supplied price, exactly as in the
        supplied-price ordering. The exit executes regardless of the
        last price's age; staleness is journaled as a data-quality
        fact — with Gate 2A's P-A1-1 UNSET, the age is recorded with
        ``staleness_threshold: "NOT_SET"`` and no verdict."""
        if self._recovery_block is not None:
            return None
        open_exec, _pos = self._open_b_position_locked()
        if open_exec is None:
            return None
        session_date = self._session_date_et(open_exec)
        if session_date is None or session_date != now_et.date():
            return None
        deadline = datetime.combine(session_date, B_PAPER_TIME_EXIT_ET,
                                      tzinfo=ET_ZONE)
        if now_et < deadline:
            return None
        last = self._last_tape()
        if last is None:
            # No price has ever been supplied to this bridge; there
            # is no honest price to close at, and an exit cannot be
            # booked without one. The deadline miss is journaled as
            # an exception fact (once per process — final review
            # round, Item A) and the position remains open and
            # visible; it is never closed at an invented price. (An
            # open position's own fill is recorded on the tape at
            # execution, so an empty tape means the tape itself was
            # lost — a state the journal must state, not absorb.)
            self._journal_scheduled_exit_no_price(
                open_exec, session_date, deadline, now_et)
            return None
        price = float(last["price"])
        exit_entry = _run(self.server._check_bracket_exits(price))
        if exit_entry:
            return self._mirror_exit_locked(exit_entry)
        age_seconds = None
        if last.get("source_epoch") is not None:
            age_seconds = round(deadline.timestamp()
                                - float(last["source_epoch"]), 3)
        evidence: Dict[str, Any] = {
            "rule": "16:00 ET on the position's session date"
                    " (founder-approved Strategy B paper profile,"
                    " Nov 21, 2026; Amendment A1 Mechanism 1)",
            "mechanism": "SCHEDULED",
            "session_date": session_date.isoformat(),
            "deadline_et": deadline.isoformat(),
            "exit_ts_et": now_et.isoformat(),
            "price": price,
            "price_source_ts": last.get("source_ts"),
            "price_age_seconds": age_seconds,
            "price_basis": "SUPPLIED_TAPE",
            "fill_basis": "the most recent price supplied to the"
                          " bridge (its recorded tape); the bridge"
                          " reads no market feed and this price is"
                          " not a live market quote",
        }
        if age_seconds is not None and age_seconds < 0:
            # The most recent tape price is stamped AFTER the
            # deadline (e.g. the position's own fill, recorded from
            # a record stamped past 16:00 ET). The computed age is
            # negative; it is journaled as computed — never clamped
            # into a plausible-looking value — and flagged here so
            # no reader mistakes the exit price for a price that
            # existed at the deadline.
            evidence["price_stamped_after_deadline"] = True
        threshold = self._staleness_threshold_seconds
        if threshold is None:
            evidence["staleness_threshold"] = "NOT_SET"
        else:
            evidence["staleness_threshold_seconds"] = float(threshold)
            evidence["stale"] = bool(
                age_seconds is not None and age_seconds > float(threshold))
        entry = self._book_close_locked(price, "TIME_EXIT",
                                        "time_exit", evidence)
        return self._mirror_exit_locked(entry)

    def _journal_scheduled_exit_no_price(
            self, open_exec, session_date, deadline: datetime,
            now_et: datetime) -> None:
        """Final review round, Item A: the 16:00 ET deadline was
        reached on the open position's session date and the bridge's
        recorded tape holds NO price at all. No exit can be booked
        without a price, so the position stays open — and the miss
        is journaled as an exception fact rather than passing
        silently on every tick. Journaled once per (signal, session)
        per process; a later process that still finds the position
        open past its deadline journals its own observation (and the
        startup recovery pass owns the position from there)."""
        key = (open_exec["signal_id"], session_date.isoformat())
        if key in self._no_price_miss_journaled:
            return
        self._no_price_miss_journaled.add(key)
        entry = {
            "id": str(uuid.uuid4()),
            "ts": _now_iso(),
            "action": "SCHEDULED_EXIT_NO_PRICE",
            "symbol": "MNQ",
            "phase": "SIM_LOG_ONLY",
            "origin": "PAPER_BRIDGE",
            "bridge": {
                "signal_id": open_exec["signal_id"],
                "strategy_id": open_exec.get("strategy_id"),
                "session_date": session_date.isoformat(),
                "deadline_et": deadline.isoformat(),
                "tick_ts_et": now_et.isoformat(),
                "note": "the 16:00 ET deadline was reached on the"
                        " position's session date, but no price has"
                        " ever been supplied to the bridge's recorded"
                        " tape; no exit was booked — an exit cannot"
                        " be booked without a price — and the"
                        " position remains open",
                "risk_approval_status": sc.RISK_UNAPPROVED,
            },
        }
        self._journal("SCHEDULED_EXIT_NO_PRICE", entry)

    def tick_time_exit(self, now=None) -> Optional[Dict[str, Any]]:
        """Drive Mechanism 1's scheduler once (see TimeExitScheduler).
        ``now`` is an injectable instant (datetime or ISO string);
        the service loop calls this with no argument."""
        return self.time_exit_scheduler.tick(now)

    # -- Amendment A1 Mechanism 2: startup recovery -----------------------

    def _deadline_for(self, open_exec) -> Optional[datetime]:
        session_date = self._session_date_et(open_exec)
        if session_date is None:
            return None
        return datetime.combine(session_date, B_PAPER_TIME_EXIT_ET,
                                tzinfo=ET_ZONE)

    def _journal_recovery_block(self, event: str) -> None:
        block = self._recovery_block or {}
        open_exec = self.open_execution()
        record = (open_exec or {}).get("record") or {}
        risk_decision = {
            "outcome": f"RECOVERY_BLOCK_{event}",
            "reason": R_RECOVERY_BLOCK,
            "detail": ("restart recovery " + event.lower() + ": a"
                       " Strategy B position past its session"
                       " deadline is unrecovered; new automated"
                       " entries are blocked until it closes"
                       if event == "RAISED" else
                       "restart recovery lifted: the past-deadline"
                       " Strategy B position is closed; new automated"
                       " entries are evaluated on their merits again"),
            "risk_approval_status": sc.RISK_UNAPPROVED,
            "recovery_block": dict(block, event=event),
        }
        entry = self._base_entry(record, None, risk_decision,
                                 "RECOVERY_BLOCK", reason=R_RECOVERY_BLOCK)
        entry["bridge"]["recovery_block"] = dict(block, event=event)
        self._journal("RECOVERY_BLOCK", entry)

    def _lift_recovery_block(self) -> None:
        self._journal_recovery_block("LIFTED")
        self._recovery_block = None

    def _startup_recovery(self) -> None:
        """Mechanism 2 (Amendment A1 §A1.3.2): the startup
        reconciliation pass. Runs after rehydration, before any new
        automated entry is accepted.

        An open Strategy B position whose session deadline (16:00 ET
        of its session date) has already passed is detected and
        blocks new automated entries (journaled RECOVERY_BLOCK). If a
        verifiable deadline-window price exists on the recorded tape,
        the position closes immediately at that price — TIME_EXIT,
        ``recovered: true`` — and the block lifts. Otherwise the
        block persists: the position closes at the first price
        supplied after startup, as LATE_EXIT_EXCEPTION, through
        :meth:`_recovery_resolve_locked`. A position whose deadline
        has NOT passed is not this pass's case (Path 2c): no block,
        no exit — Mechanism 1 owns it when the deadline arrives."""
        with self._lock:
            open_exec, _pos = self._open_b_position_locked()
            if open_exec is None:
                return
            deadline = self._deadline_for(open_exec)
            if deadline is None or self._now_et() < deadline:
                return
            session_date = self._session_date_et(open_exec)
            self._recovery_block = {
                "signal_id": open_exec["signal_id"],
                "session_date": session_date.isoformat()
                if session_date else None,
                "deadline_et": deadline.isoformat(),
                "raised_ts": _now_iso(),
                "state": "BLOCKED — RECOVERY PENDING",
            }
            self._journal_recovery_block("RAISED")
            qualified = self._deadline_window_price(deadline)
            if qualified is not None:
                evidence = {
                    "rule": "16:00 ET on the position's session date"
                            " (founder-approved Strategy B paper"
                            " profile, Nov 21, 2026; Amendment A1"
                            " Mechanism 2)",
                    "mechanism": "RESTART_RECOVERY",
                    "recovered": True,
                    "session_date": self._recovery_block["session_date"],
                    "deadline_et": deadline.isoformat(),
                    "price": float(qualified["price"]),
                    "price_source_ts": qualified.get("source_ts"),
                    "price_basis": "SUPPLIED_TAPE",
                    "recovery_window_seconds":
                        float(self._recovery_window_seconds),
                    "fill_basis": "the latest price recorded on the"
                                  " bridge's own tape inside the"
                                  " recovery window; reproducible"
                                  " from the journal alone",
                }
                entry = self._book_close_locked(
                    float(qualified["price"]), "TIME_EXIT",
                    "time_exit", evidence)
                self._mirror_exit_locked(entry)

    def _recovery_resolve_locked(self, price: float,
                                 update_et: Optional[datetime]
                                 ) -> Optional[Dict[str, Any]]:
        """Resolve the blocked position on a newly supplied price
        (bracket exits have already had their claim on it). The
        window search runs over the whole recorded tape — including
        the price just recorded — because a verifiable deadline price
        is defined by its SOURCE timestamp, whenever it arrived. A
        qualifying price closes the position as a recovered TIME_EXIT;
        anything else closes it at THIS price as LATE_EXIT_EXCEPTION,
        with the full discrepancy journaled. The block lifts in
        :meth:`_mirror_exit_locked`."""
        open_exec, _pos = self._open_b_position_locked()
        if open_exec is None:
            return None
        deadline = self._deadline_for(open_exec)
        if deadline is None:
            return None
        qualified = self._deadline_window_price(deadline)
        if qualified is not None:
            evidence = {
                "rule": "16:00 ET on the position's session date"
                        " (founder-approved Strategy B paper profile,"
                        " Nov 21, 2026; Amendment A1 Mechanism 2)",
                "mechanism": "RESTART_RECOVERY",
                "recovered": True,
                "session_date": (self._recovery_block or {}).get(
                    "session_date"),
                "deadline_et": deadline.isoformat(),
                "price": float(qualified["price"]),
                "price_source_ts": qualified.get("source_ts"),
                "price_basis": "SUPPLIED_TAPE",
                "recovery_window_seconds":
                    float(self._recovery_window_seconds),
                "fill_basis": "the latest price recorded on the"
                              " bridge's own tape inside the recovery"
                              " window; reproducible from the journal"
                              " alone",
            }
            return self._book_close_locked(
                float(qualified["price"]), "TIME_EXIT",
                "time_exit", evidence)
        exit_et = update_et if update_et is not None else self._now_et()
        window = self._recovery_window_seconds
        evidence = {
            "rule": "16:00 ET on the position's session date"
                    " (founder-approved Strategy B paper profile,"
                    " Nov 21, 2026; Amendment A1 Mechanism 2)",
            "mechanism": "RESTART_RECOVERY",
            "recovered": False,
            "session_date": (self._recovery_block or {}).get(
                "session_date"),
            "deadline_et": deadline.isoformat(),
            "actual_exit_ts_et": exit_et.isoformat(),
            "exit_price": float(price),
            "price_source_ts": update_et.isoformat()
            if update_et is not None else None,
            "price_source": "the first price supplied to the bridge"
                            " after the restart",
            "price_basis": "SUPPLIED_TAPE",
            "lateness_seconds": round(
                (exit_et - deadline).total_seconds(), 3),
            "recovery_failure_reason":
                "RECOVERY_WINDOW_NOT_SET" if window is None
                else "NO_VERIFIABLE_PRICE",
            "recovery_window": "NOT_SET" if window is None
            else float(window),
            "fill_basis": "no verifiable deadline-window price"
                          " exists in the bridge's recorded tape;"
                          " the position closes at the first"
                          " available price and the discrepancy is"
                          " preserved here — this exit is never"
                          " labeled TIME_EXIT",
        }
        return self._book_close_locked(
            price, EXIT_LATE_EXCEPTION, "late_exit_exception", evidence)

    # -- Final review round, Item D: engine↔journal consistency ---------

    def _startup_consistency_check(self) -> None:
        """Verify, at startup, that the Stage 2 engine's state and
        the bridge journal tell the same story — the crash boundary
        the completion build left unverified: the engine books an
        execution and the process dies before the bridge mirrors it
        (the mirror is the EXECUTION journal entry + the execution
        row). Before this check, the next startup silently erased
        the orphaned engine position: rehydration reads only the
        bridge journal, so the trade vanished from the joined record
        with no trace and entries stayed unblocked.

        Three surfaces are compared, all from durable or snapshotted
        state taken before this bridge reset the engine:

        (a) an EXECUTION entry in the bridge journal whose signal
            has NO execution row (death between the journal write
            and the row save, or between the engine booking and
            both);
        (b) an open position in the engine state this bridge found
            at construction (its init snapshot) that no OPEN journal
            execution accounts for — matched on the stable identity
            fields (side, qty, avg_entry) of the execution's
            resulting position;
        (c) an OPEN execution row whose position did not rehydrate
            into the engine (row present, engine flat).

        Any divergence is journaled as an explicit
        ENGINE_BRIDGE_INCONSISTENCY fact and blocks new automated
        entries (the RECOVERY_BLOCK posture) for the life of this
        bridge. The block never lifts automatically: resolution is
        a founder-reviewed act, after which a fresh bridge re-runs
        this check against the corrected records. The check runs
        only at construction — a divergence created mid-session by
        a failed mirror is surfaced by the exception at the failure
        point and detected here at the next startup."""
        divergences = []

        # (a) EXECUTION journal entries with no execution row.
        seen_rows = set()
        for row in self._db.execute(
                "SELECT entry FROM bridge_journal"
                " WHERE kind = 'EXECUTION'").fetchall():
            entry = json.loads(row["entry"])
            signal_id = (entry.get("bridge") or {}).get("signal_id") \
                or (entry.get("source_alert") or {}).get("signal_id")
            if not signal_id or signal_id in seen_rows:
                continue
            seen_rows.add(signal_id)
            if self._get_execution(signal_id) is None:
                divergences.append({
                    "type": "EXECUTION_JOURNAL_WITHOUT_EXECUTION_ROW",
                    "signal_id": signal_id,
                    "detail": "the bridge journal records an"
                              " execution the execution table has"
                              " no row for; the mirror was"
                              " interrupted",
                })

        open_exec = self.open_execution()

        # (b) The engine position found at construction, unaccounted.
        snap_pos = (self._saved_state or {}).get("position") or {}
        if snap_pos.get("side") and snap_pos.get("qty"):
            accounted = False
            if open_exec is not None:
                booked = (open_exec.get("order_entry") or {}).get(
                    "resulting_position") or {}
                accounted = (
                    booked.get("side") == snap_pos.get("side")
                    and booked.get("qty") == snap_pos.get("qty")
                    and abs(float(booked.get("avg_entry") or 0.0)
                            - float(snap_pos.get("avg_entry")
                                    or 0.0)) < 1e-9)
            if not accounted:
                divergences.append({
                    "type": "ENGINE_POSITION_NOT_IN_BRIDGE_JOURNAL",
                    "signal_id": (open_exec or {}).get("signal_id"),
                    "engine_position": {
                        "side": snap_pos.get("side"),
                        "qty": snap_pos.get("qty"),
                        "avg_entry": snap_pos.get("avg_entry"),
                    },
                    "detail": "the engine held an open position at"
                              " startup that no open bridge-journal"
                              " execution accounts for; it is NOT"
                              " silently erased from the record —"
                              " it is journaled here",
                })

        # (c) An OPEN row whose position did not rehydrate.
        if open_exec is not None:
            pos = self.server._operator_state["position"]
            if not pos.get("side") or not pos.get("qty"):
                divergences.append({
                    "type": "BRIDGE_JOURNAL_POSITION_NOT_IN_ENGINE",
                    "signal_id": open_exec["signal_id"],
                    "detail": "the bridge journal holds an open"
                              " execution whose position did not"
                              " rehydrate into the engine state",
                })

        if not divergences:
            return
        self._consistency_block = {
            "raised_ts": _now_iso(),
            "divergences": divergences,
            "state": "BLOCKED — INCONSISTENCY UNRESOLVED",
        }
        entry = {
            "id": str(uuid.uuid4()),
            "ts": _now_iso(),
            "action": "ENGINE_BRIDGE_INCONSISTENCY",
            "symbol": "MNQ",
            "phase": "SIM_LOG_ONLY",
            "origin": "PAPER_BRIDGE",
            "bridge": {
                "signal_id": None,
                "strategy_id": None,
                "divergences": divergences,
                "note": "startup consistency check: the Stage 2"
                        " engine's state and the bridge journal"
                        " disagree (see divergences); the divergence"
                        " is recorded, never silently absorbed, and"
                        " new automated entries are blocked until"
                        " it is resolved or founder-reviewed",
                "risk_approval_status": sc.RISK_UNAPPROVED,
            },
        }
        self._journal("ENGINE_BRIDGE_INCONSISTENCY", entry)

    # -- status surface -----------------------------------------------------

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return self._status_locked()

    def _status_locked(self) -> Dict[str, Any]:
        """Truthful joined state of the chain. Words are chosen so the
        surface can never claim LIVE / CONNECTED / EXECUTING /
        PROFITABLE: the provider is NOT_CONNECTED, the environment is
        PAPER, and every fill is SIMULATED."""
        srv = self.server
        state = srv._operator_state

        pipeline_info: Dict[str, Any] = {"records_journaled": None,
                                         "rejections_journaled": None,
                                         "latest_signal_id": None}
        if self._signal_store_path:
            try:
                from signal_pipeline import SignalStore

                store = SignalStore(self._signal_store_path)
                try:
                    pipeline_info["records_journaled"] = store.count()
                    pipeline_info["rejections_journaled"] = \
                        store.rejection_count()
                    latest = {}
                    for strat in (sc.STRATEGY_A, sc.STRATEGY_B):
                        rec = store.latest_qualified(strat, "MNQ")
                        latest[strat] = (rec or {}).get("signal_id")
                    pipeline_info["latest_qualified_signal_id"] = latest
                finally:
                    store.close()
            except Exception as exc:  # surface the failure, never hide it
                pipeline_info["error"] = str(exc)

        strategies: Dict[str, Any] = {}
        for strat in (sc.STRATEGY_A, sc.STRATEGY_B):
            row = self._db.execute(
                "SELECT signal_id, status, reason, risk_decision"
                " FROM bridge_executions WHERE strategy_id = ?"
                " ORDER BY updated_ts DESC LIMIT 1", (strat,)).fetchone()
            strategies[strat] = None if row is None else {
                "last_signal_id": row["signal_id"],
                "last_outcome": row["status"],
                "last_reason": row["reason"],
            }

        executions = []
        for row in self._db.execute(
                "SELECT signal_id, status, strategy_id, order_entry,"
                " exit_entry, reason FROM bridge_executions"
                " ORDER BY created_ts").fetchall():
            executions.append({
                "signal_id": row["signal_id"],
                "strategy_id": row["strategy_id"],
                "status": row["status"],
                "reason": row["reason"],
                "order": json.loads(row["order_entry"])
                if row["order_entry"] else None,
                "exit": json.loads(row["exit_entry"])
                if row["exit_entry"] else None,
            })

        reviews = self._db.execute(
            "SELECT COUNT(*) AS n FROM bridge_executions"
            " WHERE review IS NOT NULL").fetchone()["n"]
        journal_count = self._db.execute(
            "SELECT COUNT(*) AS n FROM bridge_journal").fetchone()["n"]

        return {
            "surface": "paper_bridge_status",
            "environment": "PAPER",
            "data_label": "PAPER",
            "pipeline": pipeline_info,
            "strategies": strategies,
            "analyst": {
                "consumer": "app/analyst_signals (Command tree)",
                "provider_status": "NOT_CONNECTED",
                "explanation_source": PROVIDER_LABEL,
                "reviews_recorded": int(reviews),
            },
            "paper": {
                "position": copy.deepcopy(state["position"]),
                "executions": executions,
                "fills_source": "SIMULATED",
                "journal_entries": int(journal_count),
            },
            "risk": {
                "automation_paused": bool(state["automation_paused"]),
                "kill_switch": bool(state["kill_switch"]),
                # Amendment A1 Mechanism 2: while a past-deadline
                # Strategy B position awaits its recovery exit, new
                # automated entries are blocked — stated plainly, in
                # the design's own claims-clean wording.
                "automated_entries":
                    "BLOCKED — RECOVERY PENDING"
                    if self._recovery_block is not None
                    else "BLOCKED — INCONSISTENCY UNRESOLVED"
                    if self._consistency_block is not None
                    else "NOT BLOCKED",
                "recovery_block": None if self._recovery_block is None
                else dict(
                    self._recovery_block,
                    detail="a Strategy B position from a prior"
                           " session is past its 16:00 ET deadline"
                           " and has not been closed by restart"
                           " recovery; new automated entries stay"
                           " blocked until it closes"),
                "consistency_block":
                    None if self._consistency_block is None
                    else dict(
                        self._consistency_block,
                        detail="the startup consistency check found"
                               " the Stage 2 engine's state and the"
                               " bridge journal in disagreement"
                               " (journaled as"
                               " ENGINE_BRIDGE_INCONSISTENCY); new"
                               " automated entries stay blocked"
                               " until the divergence is resolved"
                               " or founder-reviewed"),
                "daily_pnl": state["daily_pnl"],
                "daily_trades": state["daily_trades"],
                "max_daily_loss": state["max_daily_loss"],
                "max_daily_trades": state["max_daily_trades"],
                "paper_profile": {"qty": PAPER_PROFILE_QTY,
                                  "target_r": PAPER_PROFILE_TARGET_R},
                "strategy_b_paper_profile":
                    strategy_b_paper_profile_block(),
                "strategy_a_automation": "ATTENDED_ONLY — Strategy A"
                                         " records are reviewed and"
                                         " journaled as held, never"
                                         " auto-executed (founder"
                                         " decision, Nov 21, 2026)",
                "max_order_qty": srv.MAX_ORDER_QTY,
                "max_bracket_ticks": srv.MAX_BRACKET_TICKS,
                "risk_approval_status": sc.RISK_UNAPPROVED,
            },
            "connectivity": {
                "provider": "NOT_CONNECTED",
                "market_data": "LOCAL_ONLY — no live feed is read by"
                               " this bridge; the tape is set from"
                               " signal records and supplied prices",
            },
        }

    # -- lifecycle ------------------------------------------------------------

    def close(self) -> None:
        """Restore the engine module state snapshotted at init."""
        srv = self.server
        srv._operator_state.clear()
        srv._operator_state.update(self._saved_state)
        srv.db = self._saved_db
        if self._saved_discord is not None:
            srv.send_discord_signal = self._saved_discord
        self._db.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False
