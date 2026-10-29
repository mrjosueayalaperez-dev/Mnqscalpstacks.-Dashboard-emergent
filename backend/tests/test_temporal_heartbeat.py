"""Temporal heartbeat skeleton — runs locally with the time-skipping test server (no live services)."""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
pytest.importorskip("temporalio")

from temporalio.testing import ActivityEnvironment, WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from temporal.activities.heartbeat import heartbeat_activity  # noqa: E402
from temporal.workflows.heartbeat import HeartbeatWorkflow  # noqa: E402


@pytest.mark.asyncio
async def test_heartbeat_activity_unit():
    out = await ActivityEnvironment().run(heartbeat_activity, "unit")
    assert out["ok"] is True and out["note"] == "unit" and out["worker_host"]


@pytest.mark.asyncio
async def test_heartbeat_workflow_end_to_end():
    async with await WorkflowEnvironment.start_time_skipping() as env:
        tq = f"test-{uuid.uuid4()}"
        async with Worker(env.client, task_queue=tq, workflows=[HeartbeatWorkflow], activities=[heartbeat_activity]):
            out = await env.client.execute_workflow(HeartbeatWorkflow.run, "e2e", id=f"hb-{uuid.uuid4()}", task_queue=tq)
    assert out["ok"] is True and out["note"] == "e2e"
