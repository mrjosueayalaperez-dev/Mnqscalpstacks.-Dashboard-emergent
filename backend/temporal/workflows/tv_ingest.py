"""TvIngestWorkflow: idempotent, audited TradingView signal ingest (display-only, no orders)."""
from datetime import timedelta
from typing import Any, Dict

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from temporal.activities.tv_ingest import notify_discord, persist_signal, validate_and_price, write_audit

_T = timedelta(seconds=10)


@workflow.defn
class TvIngestWorkflow:
    @workflow.run
    async def run(self, p: Dict[str, Any]) -> Dict[str, Any]:
        wid = workflow.info().workflow_id
        audit = {"workflow_id": wid, "run_id": workflow.info().run_id, "route": p.get("route"),
                 "payload_sha256": p.get("payload_sha256"), "action": p.get("action"),
                 "symbol": p.get("symbol"), "source": p.get("source", ""),
                 "received_at_api_utc": p.get("received_at")}
        try:
            v = await workflow.execute_activity(validate_and_price, p, start_to_close_timeout=_T,
                                                retry_policy=RetryPolicy(maximum_attempts=3))
        except ActivityError as e:
            cause = e.cause
            status = cause.details[0] if isinstance(cause, ApplicationError) and cause.details else 400
            detail = cause.message if isinstance(cause, ApplicationError) else "validation failed"
            await workflow.execute_activity(write_audit, {**audit, "result": "rejected", "duplicate": False,
                                                          "http_status": status, "event_ok": False,
                                                          "event_detail": detail, "discord_sent": False},
                                            start_to_close_timeout=_T)
            return {"http_status": status, "body": {"detail": detail}}

        r = await workflow.execute_activity(persist_signal, {**v, "ingest_key": wid}, start_to_close_timeout=_T,
                                            retry_policy=RetryPolicy(maximum_attempts=3))
        sent = False
        if r.get("notify") and r.get("signal_id"):
            sent = await workflow.execute_activity(
                notify_discord, r["signal_id"], start_to_close_timeout=_T,
                retry_policy=RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=1),
                                         backoff_coefficient=2.0))
        ok, detail = r.get("event", [True, r.get("result")])
        await workflow.execute_activity(write_audit, {**audit, "result": r.get("result"),
                                                      "duplicate": r.get("result") == "duplicate",
                                                      "signal_id": r.get("signal_id"), "http_status": 200,
                                                      "event_ok": ok, "event_detail": detail,
                                                      "discord_sent": bool(sent)},
                                        start_to_close_timeout=_T)
        return {"http_status": 200, "body": r["body"]}
