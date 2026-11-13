"""Mock-only tests for scripts/add_paper_trades_2026-10-29.py (never touches a real database)."""
import importlib.util
import os

import pytest

mongomock = pytest.importorskip("mongomock")
_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "add_paper_trades_2026-10-29.py")
spec = importlib.util.spec_from_file_location("add_paper_trades", _PATH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def _db():
    db = mongomock.MongoClient()["t"]
    db.trades.insert_one({"id": "existing", "symbol": "MNQ", "pnl": 10.0, "notes": "SIM | other"})
    return db


def test_dry_run_writes_nothing():
    db = _db()
    res = mod.run(db, apply=False, out=lambda *_: None)
    assert res["inserted"] == [] and res["day_net"] == 2493.60
    assert db.trades.count_documents({}) == 1


def test_apply_inserts_exactly_two_paper_rows():
    db = _db()
    res = mod.run(db, apply=True, out=lambda *_: None)
    assert res["inserted"] == ["49634819", "49669945"]
    rows = list(db.trades.find({"id": {"$ne": "existing"}}, {"_id": 0}))
    assert len(rows) == 2 and db.trades.count_documents({}) == 3
    assert sorted(r["pnl"] for r in rows) == [136.80, 2356.80]
    for r in rows:
        assert r["notes"].startswith("PAPER/SIM — not live") and r["symbol"] == "MNQ"
        assert r["quantity"] == 6 and r["side"] == "short" and r["status"] == "closed"
        assert r["entry_date"] == r["exit_date"] == "2026-10-29" and r["entry_price"] >= 25000
    assert "Order ID 54971494" in next(r for r in rows if r["pnl"] == 2356.80)["notes"]
    assert db.trades.find_one({"id": "existing"})["notes"] == "SIM | other"  # untouched


def test_rerun_refuses_duplicates():
    db = _db()
    mod.run(db, apply=True, out=lambda *_: None)
    res = mod.run(db, apply=True, out=lambda *_: None)
    assert res["inserted"] == [] and res["skipped"] == ["49634819", "49669945"]
    assert db.trades.count_documents({}) == 3


def test_missing_env_exits_without_connecting(monkeypatch):
    monkeypatch.delenv("MONGO_URL", raising=False)
    monkeypatch.delenv("DB_NAME", raising=False)
    assert mod.main([]) == 2
