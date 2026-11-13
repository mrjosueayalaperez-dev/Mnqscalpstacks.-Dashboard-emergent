"""Admin routes: admin session or X-API-Key (fail-closed when RETOOL_API_KEY unset).

Self-contained: in-memory mongo, real JWTs, no network, no live backend."""
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

KEY = "test-retool-key-123"

# (method, path) for each guarded route
ROUTES = [
    ("get", "/api/admin/overview"),
    ("get", "/api/admin/subscribers"),
    ("patch", "/api/admin/subscribers/s1/tier?tier=elite"),
    ("delete", "/api/admin/subscribers/s1"),
    ("get", "/api/admin/clicks"),
]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def ctx(monkeypatch):
    monkeypatch.setenv("RETOOL_API_KEY", KEY)
    db = mongomock_motor.AsyncMongoMockClient()["t"]
    monkeypatch.setattr(server, "db", db)
    _run(db.users.insert_one({"user_id": "u1", "email": "u1@x.test", "role": "user"}))
    _run(db.users.insert_one({"user_id": "adm", "email": "adm@x.test", "role": "admin"}))
    c = TestClient(server.app)
    hu = {"Authorization": f"Bearer {auth.create_access_token('u1', 'u1@x.test')}"}
    ha = {"Authorization": f"Bearer {auth.create_access_token('adm', 'adm@x.test')}"}
    return c, db, hu, ha


def _seed(db):
    _run(db.subscribers.delete_many({}))
    _run(db.subscribers.insert_one({"id": "s1", "email": "s@x.test", "tier": "free", "created_at": "2026-01-01"}))


def _call(c, m, p, h):
    return getattr(c, m)(p, headers=h)


@pytest.mark.parametrize("m,p", ROUTES)
def test_no_auth_401(ctx, m, p):
    c, db, _, _ = ctx
    _seed(db)
    assert _call(c, m, p, {}).status_code == 401


@pytest.mark.parametrize("m,p", ROUTES)
def test_bad_token_401(ctx, m, p):
    c, db, _, _ = ctx
    _seed(db)
    assert _call(c, m, p, {"Authorization": "Bearer bogus"}).status_code == 401


@pytest.mark.parametrize("m,p", ROUTES)
def test_normal_user_403_and_db_unchanged(ctx, m, p):
    c, db, hu, _ = ctx
    _seed(db)
    r = _call(c, m, p, hu)
    assert r.status_code == 403 and r.json()["detail"] == "Admin only"
    doc = _run(db.subscribers.find_one({"id": "s1"}))
    assert doc is not None and doc["tier"] == "free"


@pytest.mark.parametrize("m,p", ROUTES)
def test_admin_allowed(ctx, m, p):
    c, db, _, ha = ctx
    _seed(db)
    assert _call(c, m, p, ha).status_code == 200


@pytest.mark.parametrize("m,p", ROUTES)
def test_valid_api_key_allowed(ctx, m, p):
    c, db, _, _ = ctx
    _seed(db)
    assert _call(c, m, p, {"X-API-Key": KEY}).status_code == 200


@pytest.mark.parametrize("m,p", ROUTES)
def test_wrong_api_key_401(ctx, m, p):
    c, db, _, _ = ctx
    _seed(db)
    assert _call(c, m, p, {"X-API-Key": "nope"}).status_code == 401
    assert _run(db.subscribers.find_one({"id": "s1"}))["tier"] == "free"


@pytest.mark.parametrize("env", [None, ""])
@pytest.mark.parametrize("key", ["", "anything", KEY])
@pytest.mark.parametrize("m,p", ROUTES)
def test_env_key_unset_fails_closed(ctx, monkeypatch, m, p, key, env):
    c, db, _, _ = ctx
    _seed(db)
    if env is None:
        monkeypatch.delenv("RETOOL_API_KEY", raising=False)
    else:
        monkeypatch.setenv("RETOOL_API_KEY", env)
    assert _call(c, m, p, {"X-API-Key": key}).status_code == 401
    doc = _run(db.subscribers.find_one({"id": "s1"}))
    assert doc is not None and doc["tier"] == "free"
