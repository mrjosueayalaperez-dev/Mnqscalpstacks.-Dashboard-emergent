"""API-side hook: start TvIngestWorkflow from FastAPI. OFF unless TEMPORAL_ENABLED=true."""
import asyncio
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

INGEST_WAIT_SECONDS = 1.5
_CONNECT_TIMEOUT = 3.0
_client = None


class IngestUnavailable(Exception):
    """Temporal unreachable — the API answers 503 (no local fallback when enabled)."""


def temporal_enabled() -> bool:
    return os.environ.get("TEMPORAL_ENABLED", "false").strip().lower() in ("1", "true", "yes")


async def _get_client():
    global _client
    if _client is None:
        from temporal.config import connect
        _client = await asyncio.wait_for(connect(), _CONNECT_TIMEOUT)
    return _client


def reset_client() -> None:
    global _client
    _client = None


def workflow_id_for(p: Dict[str, Any], alert_time: Optional[str], now: Optional[datetime] = None) -> Tuple[str, str]:
    """Idempotency key: sha256 of the secret-free normalized payload + TradingView `time` (or UTC minute)."""
    norm = {k: p.get(k) for k in ("action", "symbol", "interval", "price", "note", "source")}
    payload_hash = hashlib.sha256(json.dumps(norm, sort_keys=True, default=str).encode()).hexdigest()
    bucket = alert_time or (now or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M")
    key = hashlib.sha256(f"{payload_hash}|{bucket}".encode()).hexdigest()[:24]
    return f"tv-ingest-{key}", payload_hash


async def run_ingest(p: Dict[str, Any], alert_time: Optional[str] = None, client=None,
                     wait: float = INGEST_WAIT_SECONDS) -> Tuple[int, Dict[str, Any]]:
    """Start (or attach to) the workflow, wait up to `wait` s. Returns (http_status, body)."""
    from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from temporal.config import TASK_QUEUE
    from temporal.workflows.tv_ingest import TvIngestWorkflow

    assert "secret" not in p, "secret must never be passed to the workflow"
    wf_id, payload_hash = workflow_id_for(p, alert_time)
    p = {**p, "payload_sha256": payload_hash, "received_at": datetime.now(timezone.utc).isoformat()}
    try:
        c = client or await _get_client()
        try:
            handle = await asyncio.wait_for(c.start_workflow(
                TvIngestWorkflow.run, p, id=wf_id, task_queue=TASK_QUEUE,
                id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
                id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING), _CONNECT_TIMEOUT)
        except WorkflowAlreadyStartedError:
            handle = c.get_workflow_handle(wf_id)  # duplicate delivery → original result
    except Exception as e:
        if client is None:
            reset_client()
        raise IngestUnavailable(str(e)) from e
    try:
        res = await asyncio.wait_for(handle.result(), wait)
    except asyncio.TimeoutError:
        return 202, {"status": "accepted", "workflow_id": wf_id}
    except Exception:  # workflow failed after retries (e.g. Mongo down) — visible in Temporal history
        return 500, {"detail": "ingest failed", "workflow_id": wf_id}
    return int(res.get("http_status", 200)), res.get("body", {})
