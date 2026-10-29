"""No-op heartbeat activity. Touches no Mongo, Yahoo, Discord, or ATI."""
import socket
from datetime import datetime, timezone

from temporalio import activity


@activity.defn
async def heartbeat_activity(note: str) -> dict:
    activity.logger.info("heartbeat ok")
    return {
        "ok": True,
        "worker_host": socket.gethostname(),
        "ts": datetime.now(timezone.utc).isoformat(),
        "note": note,
    }
