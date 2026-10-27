"""NinjaTrader ATI bridge — Phase 2 order routing.

Cloud side of the OIF (Order Instruction File) pipeline:
  cockpit order -> Mongo `ati_commands` queue -> local Python bridge polls
  `/api/ati/commands` -> writes `oif_*.txt` into Documents/NinjaTrader 8/incoming
  -> NinjaTrader executes -> bridge POSTs `/api/ati/ack`.

The bridge script itself is served at GET /api/ati/bridge-script.
"""
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict

BRIDGE_HEARTBEAT_TIMEOUT_S = 15

# In-memory ATI routing state (single-operator cockpit, mirrors _operator_state pattern)
_ati_state: Dict[str, Any] = {
    "enabled": False,            # False = simulator only, True = enqueue real OIF commands
    "account": "Sim101",
    "instrument": "MNQ 03-26",   # NinjaTrader format: ROOT + space + MM-YY
    "atm_template": "",          # default ATM strategy template name (blank = none)
    "last_heartbeat": 0.0,       # unix ts of last bridge heartbeat
}


def bridge_online() -> bool:
    return (time.time() - _ati_state["last_heartbeat"]) < BRIDGE_HEARTBEAT_TIMEOUT_S


def ati_enabled() -> bool:
    """P0 hardening: NinjaTrader ATI routing is hard-disabled. No config can enable it."""
    return False


class AtiConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: Optional[bool] = None
    account: Optional[str] = None
    instrument: Optional[str] = None
    atm_template: Optional[str] = None


class AtiAck(BaseModel):
    command_ids: List[str]


def _new_command(command_type: str, **fields: Any) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "command_type": command_type,
        "account": _ati_state["account"],
        "instrument": _ati_state["instrument"],
        "action": fields.get("action", ""),
        "quantity": fields.get("quantity", 0),
        "order_type": fields.get("order_type", ""),
        "limit_price": fields.get("limit_price"),
        "stop_price": fields.get("stop_price"),
        "tif": fields.get("tif", "DAY"),
        "atm_strategy_name": fields.get("atm_strategy_name", ""),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dispatched_at": None,
        "source_order_id": fields.get("source_order_id"),
    }


def build_ati_command_for_order(order: Any, journal_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Map an OperatorOrder to an ATI command dict (None if no ATI mapping)."""
    action = order.action
    if action in ("BUY", "SELL"):
        # ATM template: preset id (user names NT templates SNIPE_1R/SNIPE_2R/RUNNER)
        # falls back to the globally configured default template.
        atm = order.preset or _ati_state["atm_template"]
        return _new_command(
            "PLACE",
            action=action,
            quantity=order.qty,
            order_type=order.order_type,
            limit_price=order.limit_price if order.order_type == "LIMIT" else None,
            tif="DAY",
            atm_strategy_name=atm or "",
            source_order_id=journal_id,
        )
    if action in ("CLOSE_LONG", "CLOSE_SHORT"):
        return _new_command("CLOSEPOSITION", source_order_id=journal_id)
    # BREAK_EVEN has no direct OIF mapping (managed by the ATM strategy in NT)
    return None


def build_flatten_command() -> Dict[str, Any]:
    return _new_command("FLATTENEVERYTHING")


async def enqueue(db: Any, command: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """P0 hardening: hard no-op. Nothing is ever queued for a broker."""
    return None


async def _status_payload(db: Any) -> Dict[str, Any]:
    pending = await db.ati_commands.count_documents({"status": "pending"})
    dispatched = await db.ati_commands.count_documents({"status": "dispatched"})
    hb_age = time.time() - _ati_state["last_heartbeat"] if _ati_state["last_heartbeat"] else None
    return {
        "enabled": False,
        "account": _ati_state["account"],
        "instrument": _ati_state["instrument"],
        "atm_template": _ati_state["atm_template"],
        "bridge_online": bridge_online(),
        "heartbeat_age_s": round(hb_age, 1) if hb_age is not None else None,
        "pending": pending,
        "dispatched": dispatched,
    }


def build_ati_router(db: Any, require_write_key: Any) -> APIRouter:
    router = APIRouter(prefix="/ati", tags=["ati"])

    @router.get("/status")
    async def ati_status() -> Dict[str, Any]:
        """Bridge + routing status for the cockpit UI and Retool."""
        return await _status_payload(db)

    @router.get("/commands", dependencies=[Depends(require_write_key)])
    async def ati_commands(limit: int = 20) -> Dict[str, Any]:
        """Bridge polling endpoint: pending commands, oldest first."""
        rows = (
            await db.ati_commands
            .find({"status": "pending"}, {"_id": 0})
            .sort("created_at", 1)
            .limit(limit)
            .to_list(length=limit)
        )
        return {"commands": rows}

    @router.post("/ack", dependencies=[Depends(require_write_key)])
    async def ati_ack(ack: AtiAck) -> Dict[str, Any]:
        """Bridge acknowledges OIF files written — commands become 'dispatched'."""
        result = await db.ati_commands.update_many(
            {"id": {"$in": ack.command_ids}, "status": "pending"},
            {"$set": {"status": "dispatched", "dispatched_at": datetime.now(timezone.utc).isoformat()}},
        )
        return {"ok": True, "acked": result.modified_count}

    @router.post("/heartbeat", dependencies=[Depends(require_write_key)])
    async def ati_heartbeat() -> Dict[str, Any]:
        """Bridge liveness ping (sent every poll cycle)."""
        _ati_state["last_heartbeat"] = time.time()
        return {"ok": True, "bridge_online": True}

    @router.get("/bridge-script", response_class=PlainTextResponse)
    async def ati_bridge_script() -> PlainTextResponse:
        """Download the single-file Windows bridge script (Python 3, stdlib only)."""
        """Disabled (P0): NinjaTrader bridge is not distributed."""
        return PlainTextResponse("NinjaTrader bridge disabled.", status_code=410)

    return router
