"""Paper bridge status surface — the minimum truthful API for the join.

One read-only endpoint, ``GET /api/paper-bridge/status``, exposing the
joined chain's actual state (see ``paper_bridge.PaperBridge.status``):
pipeline journal counts and latest qualified signal, per-strategy last
outcomes, Analyst state with the verbatim provider label, paper
positions and simulated order/fill history, risk state (paused, profile,
UNAPPROVED), and connectivity stated plainly as NOT_CONNECTED.

The bridge instance is a process-wide singleton created lazily on first
use: constructing a PaperBridge binds the Stage 2 engine's operator
state for its session, so it must happen exactly once per process —
never per request. Scope: this surface serves the LOCAL integrated
system (the bridge's own deployment shape); it reads the bridge's
durable journal and the pipeline's signal store, and it mutates nothing.

The endpoint is a plain ``def`` (FastAPI runs it in a threadpool): the
bridge's engine calls use ``asyncio.run``, which requires a thread
without a running event loop.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from fastapi import APIRouter

import paper_bridge as pb
from signal_pipeline import default_store_path

_bridge: Optional[pb.PaperBridge] = None
_lock = threading.Lock()


def get_bridge() -> pb.PaperBridge:
    """The process-wide bridge singleton (created once, lazily)."""
    global _bridge
    if _bridge is None:
        with _lock:
            if _bridge is None:
                _bridge = pb.PaperBridge(
                    signal_store_path=default_store_path())
    return _bridge


def build_paper_bridge_router() -> APIRouter:
    router = APIRouter(prefix="/paper-bridge", tags=["operator"])

    @router.get("/status")
    def paper_bridge_status() -> Dict[str, Any]:
        """Joined paper-chain status. Read-only; every value is read
        from the actual journals and engine state at call time."""
        return get_bridge().status()

    return router
