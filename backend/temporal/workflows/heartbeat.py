"""HeartbeatWorkflow: proves the worker polls the task queue and completes a run."""
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from temporal.activities.heartbeat import heartbeat_activity


@workflow.defn
class HeartbeatWorkflow:
    @workflow.run
    async def run(self, note: str = "heartbeat") -> dict:
        return await workflow.execute_activity(
            heartbeat_activity,
            note,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
