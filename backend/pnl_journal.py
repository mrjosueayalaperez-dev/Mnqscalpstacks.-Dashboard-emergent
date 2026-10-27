"""Apex 50K eval daily P&L journal (manual log only; places no trades).

Mongo collection: ``pnl_journal``
Document schema::

    {
      "entry_id":   str (uuid4),
      "user_id":    str   # owner; every query is scoped by this
      "date":       str   # trading day, "YYYY-MM-DD" (as entered by user)
      "mode":       str   # "TEST" | "PAPER" | "LIVE" (required, user-declared)
      "daily_pnl":  float # net P&L for the day in USD
      "note":       str | None (<= 500 chars)
      "created_at": ISO-8601 UTC str,
      "updated_at": ISO-8601 UTC str,
    }

Unique index: (user_id, date, mode). POSTing an existing (date, mode) upserts
(overwrites) that day's entry. Stats are computed per mode -- modes are never mixed.
All routes require the existing auth dependency (auth.get_current_user).
"""
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

COLLECTION = "pnl_journal"
MODES = ("TEST", "PAPER", "LIVE")
APEX_TARGET = 3000.0
APEX_TRAILING_DD = 2000.0
APEX_DAYS = 30


class JournalEntryIn(BaseModel):
    date: str = Field(..., pattern=r"^\d{4}-\d{2}-\d{2}$")
    daily_pnl: float
    mode: Literal["TEST", "PAPER", "LIVE"]
    note: Optional[str] = Field(None, max_length=500)


def compute_stats(pnls: List[float]) -> Dict[str, Any]:
    """Running total, best day, best-day % of total ('N/A' when total <= 0)."""
    total = round(sum(pnls), 2)
    best = max(pnls) if pnls else None
    if total <= 0 or best is None:
        pct: Any = "N/A"
    else:
        pct = round(best / total * 100, 2)
    progress = round(total / APEX_TARGET * 100, 2) if total > 0 else 0.0
    return {"total": total, "best_day": best, "best_day_pct": pct,
            "days": len(pnls), "target": APEX_TARGET, "target_progress_pct": progress,
            "trailing_drawdown": APEX_TRAILING_DD, "eval_days": APEX_DAYS}


def build_pnl_journal_router(db: Any, get_current_user: Callable[[Request, Any], Awaitable[Dict[str, Any]]]) -> APIRouter:
    router = APIRouter(prefix="/pnl-journal", tags=["pnl-journal"])

    @router.get("")
    async def list_entries(request: Request, mode: Literal["TEST", "PAPER", "LIVE"] = Query("TEST")):
        user = await get_current_user(request, db)
        docs = await db[COLLECTION].find({"user_id": user["user_id"], "mode": mode}, {"_id": 0}).sort("date", 1).to_list(1000)
        running, rows = 0.0, []
        for d in docs:
            running = round(running + d["daily_pnl"], 2)
            rows.append({**d, "running_total": running})
        return {"mode": mode, "entries": rows, "stats": compute_stats([d["daily_pnl"] for d in docs])}

    @router.post("")
    async def upsert_entry(body: JournalEntryIn, request: Request):
        user = await get_current_user(request, db)
        try:
            datetime.strptime(body.date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid date")
        now = datetime.now(timezone.utc).isoformat()
        key = {"user_id": user["user_id"], "date": body.date, "mode": body.mode}
        await db[COLLECTION].update_one(
            key,
            {"$set": {"daily_pnl": float(body.daily_pnl), "note": body.note, "updated_at": now},
             "$setOnInsert": {"entry_id": str(uuid.uuid4()), "created_at": now}},
            upsert=True,
        )
        return await db[COLLECTION].find_one(key, {"_id": 0})

    @router.delete("/{entry_id}")
    async def delete_entry(entry_id: str, request: Request):
        user = await get_current_user(request, db)
        res = await db[COLLECTION].delete_one({"entry_id": entry_id, "user_id": user["user_id"]})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        return {"ok": True}

    return router


async def ensure_indexes(db: Any) -> None:
    await db[COLLECTION].create_index([("user_id", 1), ("date", 1), ("mode", 1)], unique=True)
    await db[COLLECTION].create_index("entry_id", unique=True)
