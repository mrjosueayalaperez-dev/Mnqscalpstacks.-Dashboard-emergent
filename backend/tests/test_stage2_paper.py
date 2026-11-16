"""Stage 2 (Package 4) — alert-triggered paper trading: unit/integration tests.

Offline: mongomock db, stubbed Discord, fixed feed price. Covers the synthetic
test pack cases that are exercisable at this level: automation default OFF,
auto BUY/SELL with alert identity, duplicate suppression, HOLD, auto CLOSE,
bracket exits (TP/SL), kill/limit blocks, restart persistence, opposing-qty
fills, journal-failure surfacing, missing-parameter refusal.
"""
import asyncio
import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:1")  # never contacted

mongomock_motor = pytest.importorskip("mongomock_motor")

import server  # noqa: E402

SECRET = "s" * 32
KEY = "k" * 32
PRICE = 25000.0


def _pristine_state():
    return {
        "connection": {"broker": "NinjaTrader", "status": "DISCONNECTED", "account": "Sim101"},
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
        "position": {"side": None, "qty": 0, "avg_entry": 0.0, "unrealized_pnl": 0.0,
                     "sl_price": None, "tp_price": None},
    }


@pytest.fixture()
def srv(monkeypatch):
    from mongomock_motor import AsyncMongoMockClient
    mdb = AsyncMongoMockClient()["stage2_test"]
    monkeypatch.setattr(server, "db", mdb)
    monkeypatch.setattr(server, "RETOOL_API_KEY", KEY)
    monkeypatch.setattr(server, "SIGNAL_WEBHOOK_SECRET", SECRET)

    async def _no_discord(*a, **k):
        return None
    monkeypatch.setattr(server, "send_discord_signal", _no_discord)
    monkeypatch.setattr(server, "get_last_mnq", lambda: {"price": PRICE})

    async def _refresh():
        return {"price": PRICE}
    monkeypatch.setattr(server, "refresh_mnq", _refresh)

    saved_state = copy.deepcopy(server._operator_state)
    saved_kill = server.signal_engine_state["kill_switch"]
    server._operator_state.clear()
    server._operator_state.update(copy.deepcopy(_pristine_state()))
    server.signal_engine_state["kill_switch"] = False
    server._test_db = mdb
    yield server
    # Never leak mutated module state into other suites sharing this process.
    server._operator_state.clear()
    server._operator_state.update(saved_state)
    server.signal_engine_state["kill_switch"] = saved_kill


@pytest.fixture()
def client(srv):
    from fastapi.testclient import TestClient
    return TestClient(srv.app)


def _alert(client, payload):
    return client.post("/api/signals/tradingview", json=payload,
                       headers={"X-Webhook-Secret": SECRET})


def _buy_alert(**over):
    p = {"action": "BUY", "symbol": "MNQ1!", "interval": "1", "price": PRICE,
         "qty": 1, "sl_ticks": 40, "tp_ticks": 40, "source": "stage2-test"}
    p.update(over)
    return p


def _run(coro):
    """Run a coroutine without disturbing the ambient event loop other
    suites rely on (asyncio.run() unsets it on exit)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def _orders(srv):
    return _run(_collect(srv._test_db.operator_orders))


async def _collect(coll):
    return [d async for d in coll.find({})]


def _enable(srv):
    srv._operator_state["automation_paused"] = False
    srv._operator_state["last_order_at"] = 0.0


# --- Case 11: automation defaults OFF -------------------------------------

def test_automation_off_by_default_no_trade(client, srv):
    r = _alert(client, _buy_alert())
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "created"
    assert body["auto_execution"]["status"] == "skipped"
    assert body["auto_execution"]["reason"] == "automation_off"
    assert _orders(srv) == []
    assert srv._operator_state["position"]["side"] is None


# --- Case 1: BUY executes exactly one long, traceable to the alert ---------

def test_auto_buy_one_long_with_alert_identity(client, srv):
    _enable(srv)
    r = _alert(client, _buy_alert())
    body = r.json()
    assert body["auto_execution"]["status"] == "executed"
    pos = srv._operator_state["position"]
    assert pos["side"] == "LONG" and pos["qty"] == 1
    assert pos["avg_entry"] == PRICE
    assert pos["sl_price"] == PRICE - 10 and pos["tp_price"] == PRICE + 10  # 40 ticks = 10 pts
    orders = _orders(srv)
    assert len(orders) == 1
    assert orders[0]["origin"] == "AUTO"
    assert orders[0]["source_alert"]["signal_id"] == body["signal_id"]
    assert orders[0]["phase"] == "SIM_LOG_ONLY"


# --- Case 2: SELL executes exactly one short -------------------------------

def test_auto_sell_one_short(client, srv):
    _enable(srv)
    r = _alert(client, _buy_alert(action="SELL"))
    assert r.json()["auto_execution"]["status"] == "executed"
    pos = srv._operator_state["position"]
    assert pos["side"] == "SHORT" and pos["qty"] == 1
    assert pos["sl_price"] == PRICE + 10 and pos["tp_price"] == PRICE - 10


# --- Case 3: duplicate alert creates nothing -------------------------------

def test_duplicate_alert_no_second_trade(client, srv):
    _enable(srv)
    _alert(client, _buy_alert())
    srv._operator_state["last_order_at"] = 0.0
    r2 = _alert(client, _buy_alert())
    assert r2.json()["status"] == "duplicate"
    assert "auto_execution" not in r2.json()
    assert len(_orders(srv)) == 1
    assert srv._operator_state["daily_trades"] == 1


# --- Case 4: HOLD never trades ----------------------------------------------

def test_hold_never_trades(client, srv):
    _enable(srv)
    r = _alert(client, {"action": "HOLD", "symbol": "MNQ1!", "price": PRICE,
                        "source": "stage2-test"})
    assert r.status_code == 200
    assert _orders(srv) == []
    assert srv._operator_state["position"]["side"] is None


# --- Case 5: CLOSE closes the corresponding position ------------------------

def test_auto_close_closes_position(client, srv):
    _enable(srv)
    _alert(client, _buy_alert())
    srv._operator_state["last_order_at"] = 0.0
    r = _alert(client, {"action": "CLOSE", "symbol": "MNQ1!", "source": "stage2-test"})
    body = r.json()
    assert body["auto_close"]["status"] == "executed"
    assert srv._operator_state["position"]["side"] is None
    orders = _orders(srv)
    assert len(orders) == 2
    assert orders[1]["action"] == "CLOSE_LONG"
    assert orders[1]["origin"] == "AUTO"


# --- Case 6: brackets fire automatically (TP then SL) ------------------------

def test_bracket_take_profit_fires_on_tape(client, srv):
    _enable(srv)
    _alert(client, _buy_alert())
    r = _alert(client, {"action": "PRICE", "symbol": "MNQ1!", "price": PRICE + 10,
                        "source": "stage2-test"})
    body = r.json()
    assert body["exit"]["reason"] == "TAKE_PROFIT"
    assert body["exit"]["pnl"] == 20.0  # +10 pts x 1 x $2
    assert srv._operator_state["position"]["side"] is None
    exits = [o for o in _orders(srv) if o.get("exit_reason") == "TAKE_PROFIT"]
    assert len(exits) == 1 and exits[0]["origin"] == "ENGINE"


def test_bracket_stop_loss_fires_on_tape(client, srv):
    _enable(srv)
    _alert(client, _buy_alert(action="SELL"))
    r = _alert(client, {"action": "PRICE", "symbol": "MNQ1!", "price": PRICE + 10,
                        "source": "stage2-test"})
    body = r.json()
    assert body["exit"]["reason"] == "STOP_LOSS"
    assert body["exit"]["pnl"] == -20.0
    assert srv._operator_state["position"]["side"] is None


# --- Case 7: kill switch and daily limits block ------------------------------

def test_kill_switch_blocks_signal(client, srv):
    _enable(srv)
    # Signal-layer kill switch: the webhook refuses the alert outright.
    srv.signal_engine_state["kill_switch"] = True
    r = _alert(client, _buy_alert())
    assert r.json()["status"] == "blocked"
    assert _orders(srv) == []
    # Operator-layer kill switch: the alert is recorded, execution is blocked.
    srv.signal_engine_state["kill_switch"] = False
    srv._operator_state["kill_switch"] = True
    r2 = _alert(client, _buy_alert())
    body = r2.json()
    assert body["status"] == "created"
    assert body["auto_execution"]["status"] == "blocked"
    assert "kill_switch" in body["auto_execution"]["reason"].lower()
    assert _orders(srv) == []


def test_daily_loss_limit_blocks_auto(client, srv):
    _enable(srv)
    srv._operator_state["daily_pnl"] = -150.0  # beyond -100 max daily loss
    r = _alert(client, _buy_alert())
    body = r.json()
    assert body["auto_execution"]["status"] == "blocked"
    assert "daily loss" in body["auto_execution"]["reason"].lower()
    assert _orders(srv) == []


# --- Case 9: restart persistence (position + risk state) ---------------------

def test_state_persistence_roundtrip(srv):
    srv._operator_state["daily_pnl"] = -42.5
    srv._operator_state["daily_trades"] = 3
    srv._operator_state["kill_switch"] = True
    srv._operator_state["position"] = {"side": "LONG", "qty": 2, "avg_entry": 24990.0,
                                       "unrealized_pnl": 0.0, "sl_price": 24980.0,
                                       "tp_price": 25000.0}
    _run(srv._persist_operator_state())
    saved = copy.deepcopy(srv._operator_state)
    srv._operator_state.clear()
    srv._operator_state.update(copy.deepcopy(_pristine_state()))
    _run(srv._hydrate_operator_state())
    for k in ("daily_pnl", "daily_trades", "kill_switch", "position"):
        assert srv._operator_state[k] == saved[k], k


# --- Case 10: opposing orders are quantity-aware ------------------------------

def test_opposing_partial_then_flip(srv):
    st = srv._operator_state
    st["position"] = {"side": "SHORT", "qty": 5, "avg_entry": 100.0,
                      "unrealized_pnl": 0.0, "sl_price": 110.0, "tp_price": 90.0}
    buy2 = srv.OperatorOrder(action="BUY", qty=2)
    srv._apply_fill(buy2, 90.0)
    assert st["daily_pnl"] == 40.0  # (100-90) x 2 x $2
    assert st["position"]["side"] == "SHORT" and st["position"]["qty"] == 3
    assert st["position"]["sl_price"] == 110.0  # remainder keeps its brackets
    buy5 = srv.OperatorOrder(action="BUY", qty=5)
    srv._apply_fill(buy5, 80.0)
    assert st["daily_pnl"] == 40.0 + 120.0  # close 3 @ (100-80)x3x$2
    assert st["position"]["side"] == "LONG" and st["position"]["qty"] == 2
    assert st["position"]["avg_entry"] == 80.0


# --- Missing parameters: signal recorded, never executed ----------------------

def test_missing_exec_params_no_trade(client, srv):
    _enable(srv)
    p = _buy_alert()
    del p["qty"], p["sl_ticks"], p["tp_ticks"]
    r = _alert(client, p)
    body = r.json()
    assert body["status"] == "created"
    assert body["auto_execution"]["status"] == "skipped"
    assert body["auto_execution"]["reason"] == "missing_execution_parameters"
    assert _orders(srv) == []


# --- F3: journal failure is surfaced, not silent -------------------------------

def test_journal_failure_counted(srv, monkeypatch):
    class _BoomColl:
        async def insert_one(self, doc):
            raise RuntimeError("mongo down")

        async def replace_one(self, *a, **k):
            return None

    class _FakeDB:
        operator_orders = _BoomColl()
        operator_state = _BoomColl()

    monkeypatch.setattr(srv, "db", _FakeDB())
    order = srv.OperatorOrder(action="BUY", qty=1, order_type="LIMIT", limit_price=24000.0)
    res = _run(srv._execute_order(order))
    assert res["ok"] is True           # manual-path contract preserved
    assert res["journal_ok"] is False and res["degraded"] is True  # ...but visible
    assert srv._operator_state["journal_failures"] == 1  # ...and never silent


# --- Zelator PR #24 review corrections (Nov 16) ------------------------------
# Finding 1: persistence fails closed. Finding 2: hard ceilings.
# Finding 3: journal failure reaches the execution decision.

class _OkColl:
    async def insert_one(self, doc):
        return None

    async def replace_one(self, *a, **k):
        return None

    async def find_one(self, *a, **k):
        return None


class _DownColl:
    async def insert_one(self, doc):
        raise RuntimeError("mongo down")

    async def replace_one(self, *a, **k):
        raise RuntimeError("mongo down")

    async def find_one(self, *a, **k):
        raise RuntimeError("mongo down")


class _FakeDB2:
    def __init__(self, orders=None, state=None):
        self.operator_orders = orders or _OkColl()
        self.operator_state = state or _OkColl()

    def __getattr__(self, name):
        return _OkColl()


def test_persist_failure_forces_automation_off(srv, monkeypatch):
    monkeypatch.setattr(srv, "db", _FakeDB2(state=_DownColl()))
    srv._operator_state["automation_paused"] = False
    ok = _run(srv._persist_operator_state())
    assert ok is False
    assert srv._operator_state["persistence_ok"] is False
    assert srv._operator_state["automation_paused"] is True  # fail closed


def test_hydrate_failure_blocks_automation(client, srv, monkeypatch):
    monkeypatch.setattr(srv, "db", _FakeDB2(state=_DownColl()))
    _run(srv._hydrate_operator_state())
    assert srv._operator_state["persistence_ok"] is False
    # Even with automation otherwise enabled, the auto path refuses.
    srv._operator_state["automation_paused"] = False
    monkeypatch.setattr(srv, "db", srv._test_db)  # healthy db for the rest of the flow
    r = _alert(client, _buy_alert())
    body = r.json()
    assert body["auto_execution"]["status"] == "blocked"
    assert body["auto_execution"]["reason"] == "state_persistence_unavailable"
    assert _orders(srv) == []


def test_persistence_recovery_restores_flag(srv, monkeypatch):
    monkeypatch.setattr(srv, "db", _FakeDB2(state=_DownColl()))
    assert _run(srv._persist_operator_state()) is False
    monkeypatch.setattr(srv, "db", srv._test_db)
    assert _run(srv._persist_operator_state()) is True
    assert srv._operator_state["persistence_ok"] is True
    # Recovery does NOT auto-resume automation — that stays a human action.
    assert srv._operator_state["automation_paused"] is True


def test_oversized_alert_rejected(client, srv):
    _enable(srv)
    r = _alert(client, _buy_alert(qty=50))
    body = r.json()
    assert body["auto_execution"]["status"] == "rejected"
    assert body["auto_execution"]["reason"] == "quantity_exceeds_max_10"
    assert _orders(srv) == []
    r2 = _alert(client, _buy_alert(action="SELL", sl_ticks=5000))
    assert r2.json()["auto_execution"]["reason"] == "bracket_ticks_exceed_max_400"
    assert _orders(srv) == []


def test_validate_order_qty_ceiling(srv):
    from fastapi import HTTPException
    order = srv.OperatorOrder(action="BUY", qty=11)
    with pytest.raises(HTTPException) as ei:
        srv._validate_order(order, 9999999999.0)
    assert ei.value.status_code == 400
    order2 = srv.OperatorOrder(action="BUY", qty=1, sl_ticks=401)
    with pytest.raises(HTTPException):
        srv._validate_order(order2, 9999999999.0)


def test_auto_journal_failure_halts_automation(srv, monkeypatch):
    monkeypatch.setattr(srv, "db", _FakeDB2(orders=_DownColl()))
    srv._operator_state["automation_paused"] = False
    import json as _json
    raw = _json.dumps(_buy_alert())
    res = _run(srv._maybe_auto_execute({"signal_id": "sig-x"}, "BUY", "test", raw))
    assert res["status"] == "executed_journal_failed"  # never a clean success
    assert srv._operator_state["journal_failures"] == 1
    assert srv._operator_state["automation_paused"] is True  # explicit halt state
