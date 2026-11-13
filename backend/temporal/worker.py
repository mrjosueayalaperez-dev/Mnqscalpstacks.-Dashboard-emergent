"""Run: cd backend && python -m temporal.worker"""
import asyncio
import logging

from temporalio.worker import Worker

from temporal.activities import tv_ingest as tv_acts
from temporal.activities.heartbeat import heartbeat_activity
from temporal.config import TASK_QUEUE, connect
from temporal.workflows.heartbeat import HeartbeatWorkflow
from temporal.workflows.tv_ingest import TvIngestWorkflow


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    client = await connect()
    worker = Worker(
        client, task_queue=TASK_QUEUE,
        workflows=[HeartbeatWorkflow, TvIngestWorkflow],
        activities=[heartbeat_activity, tv_acts.validate_and_price, tv_acts.persist_signal,
                    tv_acts.notify_discord, tv_acts.write_audit],
    )
    logging.getLogger("temporal.worker").info(
        "worker started: namespace=%s task_queue=%s — polling", client.namespace, TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
