"""Lightweight first-party analytics — unique visitors, page views, user counts."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

import auth as auth_module

VALID_TIERS = {"free", "pro", "premium", "elite"}


class VisitBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    visitor_id: str
    path: str = "/"


class TierBody(BaseModel):
    email: str
    tier: str


def build_analytics_router(db: Any) -> APIRouter:
    router = APIRouter(prefix="/analytics", tags=["public"])

    @router.post("/visit")
    async def track_visit(body: VisitBody) -> Dict[str, Any]:
        """One deduped view per visitor/path/day."""
        if not body.visitor_id or len(body.visitor_id) > 64:
            return {"ok": False}
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        await db.analytics_visits.update_one(
            {"visitor_id": body.visitor_id, "path": body.path[:100], "date": date},
            {"$setOnInsert": {"ts": datetime.now(timezone.utc).isoformat()}, "$inc": {"views": 1}},
            upsert=True,
        )
        return {"ok": True}

    @router.post("/heartbeat")
    async def track_heartbeat(body: VisitBody) -> Dict[str, Any]:
        """Presence ping (every 60s from the frontend) — powers the Online Now counter."""
        if not body.visitor_id or len(body.visitor_id) > 64:
            return {"ok": False}
        await db.presence.update_one(
            {"visitor_id": body.visitor_id},
            {"$set": {"last_seen": datetime.now(timezone.utc).isoformat(), "path": body.path[:100]}},
            upsert=True,
        )
        return {"ok": True}

    @router.patch("/users/tier")
    async def set_user_tier(body: TierBody, request: Request) -> Dict[str, Any]:
        """Admin-only: manually set a user's plan tier (users + subscribers)."""
        actor = await auth_module.get_current_user(request, db)
        if actor.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Admin only")
        tier = body.tier.lower().strip()
        if tier not in VALID_TIERS:
            raise HTTPException(status_code=400, detail=f"Invalid tier. Use one of: {sorted(VALID_TIERS)}")
        email = body.email.lower().strip()
        res = await db.users.update_one({"email": email}, {"$set": {"tier": tier, "tier_manual": True}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
        await db.subscribers.update_one({"email": email}, {"$set": {"tier": tier}})
        return {"ok": True, "email": email, "tier": tier}

    @router.get("/stats", tags=["admin"])
    async def analytics_stats() -> Dict[str, Any]:
        """Private business stats for the admin panel."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        visitors_total = len(await db.analytics_visits.distinct("visitor_id"))
        visitors_today = len(await db.analytics_visits.distinct("visitor_id", {"date": today}))
        page_views = await db.analytics_visits.count_documents({})
        total_users = await db.users.count_documents({})
        total_subscribers = await db.subscribers.count_documents({})
        pro = await db.subscribers.count_documents({"tier": "pro"})
        elite = await db.subscribers.count_documents({"tier": "elite"})
        paying = pro + elite
        mrr = pro * 49 + elite * 149
        conversion = round(min((paying / visitors_total) * 100, 100.0), 2) if visitors_total else 0.0
        online_cutoff = (datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat()
        online_now = await db.presence.count_documents({"last_seen": {"$gte": online_cutoff}})
        return {
            "online_now": online_now,
            "total_users": total_users,
            "total_subscribers": total_subscribers,
            "visitors_total": visitors_total,
            "visitors_today": visitors_today,
            "page_views": page_views,
            "paying_subscribers": paying,
            "pro_count": pro,
            "elite_count": elite,
            "mrr": mrr,
            "conversion_rate": conversion,
        }

    @router.get("/users", tags=["admin"])
    async def analytics_users() -> Dict[str, Any]:
        """Registered users list for the admin panel (no password hashes)."""
        rows = (
            await db.users
            .find({}, {"_id": 0, "password_hash": 0})
            .sort("created_at", -1)
            .to_list(length=500)
        )
        return {"users": rows, "total": len(rows)}

    @router.get("/public")
    async def analytics_public() -> Dict[str, Any]:
        """Public social-proof counters for the landing page."""
        traders = await db.users.count_documents({}) + await db.subscribers.count_documents({})
        visitors = len(await db.analytics_visits.distinct("visitor_id"))
        return {"traders": traders, "visitors": visitors}

    return router
