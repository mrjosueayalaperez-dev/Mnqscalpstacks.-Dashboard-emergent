"""Unit tests for pnl_journal (self-contained: in-memory mongo, real auth dependency). Sample data is TEST mode."""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "unit-test-only-secret")
mongomock_motor = pytest.importorskip("mongomock_motor")

import auth  # noqa: E402
import pnl_journal  # noqa: E402
from pnl_journal import compute_stats  # noqa: E402


def test_ratio_on_sample_test_data():
    s = compute_stats([400, 250, -100, 600])  # TEST sample
    assert s["total"] == 1150
    assert s["best_day"] == 600
    assert s["best_day_pct"] == 52.17


@pytest.mark.parametrize("pnls", [[], [-100], [100, -100], [-50, -25]])
def test_na_when_total_non_positive(pnls):
    assert compute_stats(pnls)["best_day_pct"] == "N/A"


@pytest.fixture
def client_db():
    db = mongomock_motor.AsyncMongoMockClient()["t"]
    app = FastAPI()
    app.include_router(pnl_journal.build_pnl_journal_router(db, auth.get_current_user), prefix="/api")
    return TestClient(app), db


def test_auth_required(client_db):
    c, _ = client_db
    assert c.get("/api/pnl-journal").status_code == 401
    assert c.post("/api/pnl-journal", json={"date": "2026-10-26", "daily_pnl": 1, "mode": "TEST"}).status_code == 401
    assert c.delete("/api/pnl-journal/x").status_code == 401
    assert c.get("/api/pnl-journal", headers={"Authorization": "Bearer bogus"}).status_code == 401


def test_crud_scoped_per_user(client_db):
    import asyncio
    c, db = client_db
    for uid in ("u1", "u2"):
        asyncio.get_event_loop().run_until_complete(db.users.insert_one({"user_id": uid, "email": f"{uid}@x"}))
    h1 = {"Authorization": f"Bearer {auth.create_access_token('u1', 'u1@x')}"}
    h2 = {"Authorization": f"Bearer {auth.create_access_token('u2', 'u2@x')}"}
    for d, p in zip(["2026-10-01", "2026-10-02", "2026-10-03", "2026-10-04"], [400, 250, -100, 600]):
        assert c.post("/api/pnl-journal", json={"date": d, "daily_pnl": p, "mode": "TEST"}, headers=h1).status_code == 200
    assert c.post("/api/pnl-journal", json={"date": "2026-10-01", "daily_pnl": 1, "mode": "BOGUS"}, headers=h1).status_code == 422
    r = c.get("/api/pnl-journal?mode=TEST", headers=h1).json()
    assert r["stats"]["total"] == 1150 and r["stats"]["best_day_pct"] == 52.17
    assert [e["running_total"] for e in r["entries"]] == [400, 650, 550, 1150]
    assert c.get("/api/pnl-journal?mode=PAPER", headers=h1).json()["entries"] == []
    assert c.get("/api/pnl-journal?mode=TEST", headers=h2).json()["entries"] == []
    eid = r["entries"][0]["entry_id"]
    assert c.delete(f"/api/pnl-journal/{eid}", headers=h2).status_code == 404
    assert c.delete(f"/api/pnl-journal/{eid}", headers=h1).status_code == 200
