"""Checklist routes: auth required + per-user scoping (self-contained: in-memory mongo, real auth resolver).

Runs fully locally — no network, no live backend."""
import asyncio
import os
import sys

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("JWT_SECRET", "unit-test-only-secret")
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1")  # never contacted; db is swapped below
mongomock_motor = pytest.importorskip("mongomock_motor")

import auth  # noqa: E402
import server  # noqa: E402


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def ctx(monkeypatch):
    db = mongomock_motor.AsyncMongoMockClient()["t"]
    monkeypatch.setattr(server, "db", db)
    for uid in ("ua", "ub"):
        _run(db.users.insert_one({"user_id": uid, "email": f"{uid}@x.test"}))
    # a legacy global doc (no user_id) must never be exposed or touched via the API
    _run(db.checklist.insert_one({"id": "legacy-1", "text": "global", "completed": False, "category": "rules", "order": 0}))
    c = TestClient(server.app)  # not used as context manager -> startup hooks don't run
    ha = {"Authorization": f"Bearer {auth.create_access_token('ua', 'ua@x.test')}"}
    hb = {"Authorization": f"Bearer {auth.create_access_token('ub', 'ub@x.test')}"}
    return c, db, ha, hb


def test_unauthenticated_gets_401(ctx):
    c, _, _, _ = ctx
    bad = {"Authorization": "Bearer bogus"}
    for h in ({}, bad):
        assert c.get("/api/checklist", headers=h).status_code == 401
        assert c.post("/api/checklist", json={"text": "x"}, headers=h).status_code == 401
        assert c.patch("/api/checklist/legacy-1?completed=true", headers=h).status_code == 401
        assert c.delete("/api/checklist/legacy-1", headers=h).status_code == 401
        assert c.post("/api/checklist/reset", headers=h).status_code == 401


def test_seeds_own_copy_and_hides_legacy(ctx):
    c, db, ha, hb = ctx
    a = c.get("/api/checklist", headers=ha).json()
    b = c.get("/api/checklist", headers=hb).json()
    assert len(a) == len(server.DEFAULT_CHECKLIST) == len(b)
    assert {i["id"] for i in a}.isdisjoint({i["id"] for i in b})
    assert all("user_id" not in i for i in a)
    assert "legacy-1" not in {i["id"] for i in a + b}
    # seeding is idempotent per user
    assert len(c.get("/api/checklist", headers=ha).json()) == len(a)
    assert _run(db.checklist.count_documents({"user_id": "ua"})) == len(a)


def test_user_a_cannot_see_or_change_user_b_items(ctx):
    c, db, ha, hb = ctx
    c.get("/api/checklist", headers=ha)
    r = c.post("/api/checklist", json={"text": "B private", "category": "rules"}, headers=hb)
    assert r.status_code == 200
    b_id = r.json()["id"]
    assert _run(db.checklist.find_one({"id": b_id}))["user_id"] == "ub"

    # A can't see it
    assert b_id not in {i["id"] for i in c.get("/api/checklist", headers=ha).json()}
    # A can't toggle or delete it (404, not leaked), nor the legacy doc
    assert c.patch(f"/api/checklist/{b_id}?completed=true", headers=ha).status_code == 404
    assert c.delete(f"/api/checklist/{b_id}", headers=ha).status_code == 404
    assert c.patch("/api/checklist/legacy-1?completed=true", headers=ha).status_code == 404
    assert c.delete("/api/checklist/legacy-1", headers=ha).status_code == 404
    doc = _run(db.checklist.find_one({"id": b_id}))
    assert doc is not None and doc["completed"] is False

    # B can toggle its own item; A's reset doesn't touch B's items
    assert c.patch(f"/api/checklist/{b_id}?completed=true", headers=hb).status_code == 200
    assert c.post("/api/checklist/reset", headers=ha).status_code == 200
    assert _run(db.checklist.find_one({"id": b_id}))["completed"] is True
    # B can delete its own item
    assert c.delete(f"/api/checklist/{b_id}", headers=hb).status_code == 200
    assert _run(db.checklist.find_one({"id": b_id})) is None
    assert _run(db.checklist.find_one({"id": "legacy-1"})) is not None
