"""Lightweight first-party analytics — unique visitors, page views, user counts."""
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict


class VisitBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    visitor_id: str
    path: str = "/"


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
        return {
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
