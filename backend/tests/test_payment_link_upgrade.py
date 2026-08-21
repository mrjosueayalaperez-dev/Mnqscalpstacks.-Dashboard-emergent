"""Payment Link auto tier-upgrade regression — /api/webhook/stripe-live."""
import asyncio
import os
import uuid

import httpx
import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
BASE = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")
API = f"{BASE}/api"


def test_status_endpoint_reports_config_and_tier_map():
    r = httpx.get(f"{API}/webhook/stripe-live/status", timeout=15)
    assert r.status_code == 200
    d = r.json()
    assert "configured" in d and "signature_verification" in d
    assert d["tier_map"] == {"$49.00": "pro", "$99.99": "premium", "$149.00": "elite"}
    # No secrets leaked
    assert "sk_" not in r.text and "whsec_" not in r.text


def test_webhook_dormant_without_live_key():
    r = httpx.post(
        f"{API}/webhook/stripe-live",
        json={"type": "checkout.session.completed", "data": {"object": {"id": "cs_forged"}}},
        timeout=15,
    )
    assert r.status_code == 200
    status = httpx.get(f"{API}/webhook/stripe-live/status", timeout=15).json()
    if not status["configured"]:
        assert r.json()["status"] == "not_configured"


def test_apply_tier_upgrade_updates_user_and_is_idempotent():
    async def run():
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        import server

        db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
        email = f"pl-test-{uuid.uuid4().hex[:8]}@example.com"
        session_id = f"cs_test_{uuid.uuid4().hex[:10]}"
        await db.users.insert_one({"user_id": str(uuid.uuid4()), "email": email, "tier": "free", "role": "user"})
        try:
            changed = await server._apply_tier_upgrade(email, "premium", session_id, 9999)
            assert changed is True
            user = await db.users.find_one({"email": email})
            assert user["tier"] == "premium"
            tx = await db.payment_transactions.find_one({"session_id": session_id})
            assert tx["payment_status"] == "paid" and tx["tier"] == "premium" and tx["amount"] == 99.99
            # Second call: no change (idempotent)
            changed_again = await server._apply_tier_upgrade(email, "premium", session_id, 9999)
            assert changed_again is False
        finally:
            await db.users.delete_many({"email": email})
            await db.payment_transactions.delete_many({"session_id": session_id})
            await db.subscribers.delete_many({"email": email})

    asyncio.run(run())
