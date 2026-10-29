"""Run: cd backend && python -m temporal.start_heartbeat [note]"""
import asyncio
import json
import sys
from datetime import datetime, timezone

from temporal.config import TASK_QUEUE, connect
from temporal.workflows.heartbeat import HeartbeatWorkflow


async def main() -> None:
    note = sys.argv[1] if len(sys.argv) > 1 else "manual"
    wf_id = "heartbeat-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    client = await connect()
    result = await client.execute_workflow(HeartbeatWorkflow.run, note, id=wf_id, task_queue=TASK_QUEUE)
    print(f"workflow_id={wf_id} task_queue={TASK_QUEUE}")
    print("result=" + json.dumps(result))


if __name__ == "__main__":
    asyncio.run(main())
