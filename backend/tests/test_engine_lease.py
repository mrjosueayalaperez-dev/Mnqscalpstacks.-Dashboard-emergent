"""Cross-worker lease tests for the configured-alert engine. Fake collection, no Mongo, no network."""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:1")  # never contacted
os.environ.setdefault("JWT_SECRET", "unit-test-only-secret")

import server  # noqa: E402


class DuplicateKeyError(Exception):
    """Stand-in for pymongo's; server.try_acquire_lease matches on the class name."""


class FakeLeaseCollection:
    """Minimal async stand-in for the motor collection used by try_acquire_lease.

    Mirrors Mongo semantics: find_one_and_update returns the pre-update document
    (or None when the filter matches nothing); insert_one raises on duplicate _id.
    """

    def __init__(self) -> None:
        self.docs: dict = {}

    async def find_one_and_update(self, filt, update):
        doc = self.docs.get(filt["_id"])
        if doc is None:
            return None
        matched = False
        for cond in filt.get("$or", []):
            if "owner" in cond and doc.get("owner") == cond["owner"]:
                matched = True
            if "expires_at" in cond and doc.get("expires_at") <= cond["expires_at"]["$lte"]:
                matched = True
        if not matched:
            return None
        before = dict(doc)
        doc.update(update["$set"])
        return before

    async def insert_one(self, doc):
        if doc["_id"] in self.docs:
            raise DuplicateKeyError("E11000 duplicate key error")
        self.docs[doc["_id"]] = dict(doc)
        return SimpleNamespace(inserted_id=doc["_id"])


NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
LOCK = "configured_alert_engine"


@pytest.mark.asyncio
async def test_first_owner_acquires_and_second_is_blocked():
    col = FakeLeaseCollection()
    assert await server.try_acquire_lease(col, LOCK, "owner-a", NOW, 90) is True
    assert col.docs[LOCK]["owner"] == "owner-a"
    assert await server.try_acquire_lease(col, LOCK, "owner-b", NOW + timedelta(seconds=10), 90) is False
    assert col.docs[LOCK]["owner"] == "owner-a"


@pytest.mark.asyncio
async def test_expired_lease_can_be_taken_over():
    col = FakeLeaseCollection()
    assert await server.try_acquire_lease(col, LOCK, "owner-a", NOW, 90) is True
    later = NOW + timedelta(seconds=120)  # past the 90s TTL
    assert await server.try_acquire_lease(col, LOCK, "owner-b", later, 90) is True
    assert col.docs[LOCK]["owner"] == "owner-b"
    assert col.docs[LOCK]["expires_at"] == later + timedelta(seconds=90)


@pytest.mark.asyncio
async def test_owner_renews_while_holding():
    col = FakeLeaseCollection()
    assert await server.try_acquire_lease(col, LOCK, "owner-a", NOW, 90) is True
    first_expiry = col.docs[LOCK]["expires_at"]
    assert await server.try_acquire_lease(col, LOCK, "owner-a", NOW + timedelta(seconds=30), 90) is True
    assert col.docs[LOCK]["expires_at"] > first_expiry
    # The renewal keeps other workers out past the original expiry.
    assert await server.try_acquire_lease(col, LOCK, "owner-b", NOW + timedelta(seconds=100), 90) is False
