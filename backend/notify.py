"""Fire-and-forget Discord alerts to the owner's channel."""
import asyncio
import logging
import os

import httpx

logger = logging.getLogger(__name__)


async def _post(payload: dict) -> None:
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not url:
        return
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.warning(f"owner alert failed: {e}")


def owner_alert(title: str, description: str, color: int = 3447003) -> None:
    """Schedule a Discord embed without blocking the request."""
    payload = {
        "username": "MNQ SCALP STACKS BOT",
        "embeds": [{"title": title, "description": description, "color": color}],
    }
    try:
        asyncio.get_running_loop().create_task(_post(payload))
    except RuntimeError:
        pass  # no loop (tests) — skip silently
