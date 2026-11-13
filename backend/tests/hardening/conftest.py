"""Offline P0 hardening tests: in-memory mongomock, no network, no production URL."""
import os
import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:1")  # never contacted; db is swapped below


@pytest.fixture()
def srv(monkeypatch):
    from mongomock_motor import AsyncMongoMockClient
    import server
    mdb = AsyncMongoMockClient()["hardening_test"]
    monkeypatch.setattr(server, "db", mdb)
    monkeypatch.setattr(server, "RETOOL_API_KEY", "k" * 32)
    monkeypatch.setattr(server, "SIGNAL_WEBHOOK_SECRET", "s" * 32)

    async def _no_discord(*a, **k):
        return None
    monkeypatch.setattr(server, "send_discord_signal", _no_discord)
    server._test_db = mdb
    return server


@pytest.fixture()
def client(srv):
    from fastapi.testclient import TestClient
    return TestClient(srv.app)  # no context manager: startup loops/feeds never run
