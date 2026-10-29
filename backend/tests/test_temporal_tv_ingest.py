"""TvIngestWorkflow + activities — local only (time-skipping Temporal test server, mongomock_motor)."""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
pytest.importorskip("temporalio")
mongomock_motor = pytest.importorskip("mongomock_motor")

from temporalio import activity  # noqa: E402
from temporalio.exceptions import ApplicationError  # noqa: E402
from temporalio.testing import ActivityEnvironment, WorkflowEnvironment  # noqa: E402
from temporalio.worker import Worker  # noqa: E402

from temporal import ingest_client  # noqa: E402
from temporal.activities import tv_ingest as acts  # noqa: E402
from temporal.workflows.tv_ingest import TvIngestWorkflow  # noqa: E402

BUY = {"route": "primary", "action": "BUY", "symbol": "MNQ1!", "interval": "1", "price": 29900.25,
       "source": "pytest", "note": "", "cooldown_min": 3}


def _mocks(calls, notify_failures=0, validate_error=None):
    @activity.defn(name="validate_and_price")
    async def v(p):
        calls["validate"] += 1
        if validate_error:
            raise ApplicationError(validate_error[1], validate_error[0], type="ValidationError", non_retryable=True)
        return p

    @activity.defn(name="persist_signal")
    async def ps(p):
        calls["persist"] += 1
        return {"result": "created", "notify": True, "signal_id": "sig-1", "event": [True, "created"],
                "body": {"status": "created", "signal_id": "sig-1", "side": "long", "price": p["price"], "is_test": False}}

    @activity.defn(name="notify_discord")
    async def nd(signal_id):
        calls["notify_attempts"] += 1
        if calls["notify_attempts"] <= notify_failures:
            raise RuntimeError("discord 500")
        calls["sent"] += 1
        return True

    @activity.defn(name="write_audit")
    async def wa(rec):
        assert "secret" not in rec
        calls["audit"].append(rec)

    return [v, ps, nd, wa]


def _calls():
    return {"validate": 0, "persist": 0, "notify_attempts": 0, "sent": 0, "audit": []}


async def _run(env, calls, p, alert_time, **kw):
    async with Worker(env.client, task_queue="mnq-birthcell-main", workflows=[TvIngestWorkflow],
                      activities=_mocks(calls, **kw)):
        return await ingest_client.run_ingest(p, alert_time, client=env.client, wait=60)


@pytest.mark.asyncio
async def test_workflow_created():
    c = _calls()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        status, body = await _run(env, c, BUY, f"t-{uuid.uuid4()}")
    assert status == 200 and body["status"] == "created" and body["signal_id"] == "sig-1"
    assert c["sent"] == 1 and c["audit"][-1]["result"] == "created" and c["audit"][-1]["discord_sent"] is True


@pytest.mark.asyncio
async def test_duplicate_workflow_id_returns_original_and_discord_once():
    c = _calls()
    t = f"t-{uuid.uuid4()}"
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(env.client, task_queue="mnq-birthcell-main", workflows=[TvIngestWorkflow],
                          activities=_mocks(c)):
            first = await ingest_client.run_ingest(BUY, t, client=env.client, wait=60)
            second = await ingest_client.run_ingest(BUY, t, client=env.client, wait=60)
    assert first == second
    assert c["persist"] == 1 and c["sent"] == 1


@pytest.mark.asyncio
async def test_discord_fails_twice_then_succeeds_sent_once():
    c = _calls()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        status, body = await _run(env, c, BUY, f"t-{uuid.uuid4()}", notify_failures=2)
    assert status == 200 and c["notify_attempts"] == 3 and c["sent"] == 1


@pytest.mark.asyncio
async def test_validation_error_is_non_retryable():
    c = _calls()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        status, body = await _run(env, c, BUY, f"t-{uuid.uuid4()}", validate_error=(422, "No price available"))
    assert status == 422 and body == {"detail": "No price available"}
    assert c["validate"] == 1 and c["persist"] == 0 and c["sent"] == 0
    assert c["audit"][-1]["result"] == "rejected"


def test_workflow_id_is_secret_free_and_stable():
    a, h1 = ingest_client.workflow_id_for(BUY, "2026-10-29T14:00:00Z")
    b, h2 = ingest_client.workflow_id_for(dict(BUY), "2026-10-29T14:00:00Z")
    c, _ = ingest_client.workflow_id_for(BUY, "2026-10-29T14:01:00Z")
    assert a == b and h1 == h2 and a != c and a.startswith("tv-ingest-")
    with pytest.raises(AssertionError):
        import asyncio
        asyncio.run(ingest_client.run_ingest({**BUY, "secret": "x"}, None, client=object()))


# ---------- real activities on mongomock_motor ----------
@pytest.fixture
def mdb():
    db = mongomock_motor.AsyncMongoMockClient()[f"t{uuid.uuid4().hex[:6]}"]
    acts.set_db(db)
    yield db
    acts.set_db(None)
    acts.set_discord_sender(None)


@pytest.mark.asyncio
async def test_persist_is_idempotent_on_ingest_key(mdb):
    env = ActivityEnvironment()
    p = {**BUY, "ingest_key": "tv-ingest-abc"}
    r1 = await env.run(acts.persist_signal, p)
    r2 = await env.run(acts.persist_signal, p)
    # simulate a retry after the audit cache was lost: unique ingest_key still prevents a second insert
    await mdb.signal_ingest_audit.delete_many({})
    r3 = await env.run(acts.persist_signal, p)
    assert r1["result"] == "created" and r1["signal_id"] == r2["signal_id"] == r3["signal_id"]
    assert await mdb.signals.count_documents({"ingest_key": "tv-ingest-abc"}) == 1
    doc = await mdb.signals.find_one({"ingest_key": "tv-ingest-abc"})
    assert doc["is_test"] is False and doc["source"] == "webhook" and doc["status"] == "active"


@pytest.mark.asyncio
async def test_notify_discord_flag_prevents_second_send(mdb):
    sent = []

    async def fake(doc):
        sent.append(doc["id"])
        return True

    acts.set_discord_sender(fake)
    env = ActivityEnvironment()
    r = await env.run(acts.persist_signal, {**BUY, "ingest_key": "k-notify"})
    assert await env.run(acts.notify_discord, r["signal_id"]) is True
    assert await env.run(acts.notify_discord, r["signal_id"]) is True
    assert len(sent) == 1
    assert (await mdb.signals.find_one({"id": r["signal_id"]}))["discord_sent"] is True


@pytest.mark.asyncio
async def test_audit_doc_has_no_secret_and_logs_event_once(mdb):
    env = ActivityEnvironment()
    rec = {"workflow_id": "tv-ingest-aud", "route": "primary", "payload_sha256": "h", "action": "BUY",
           "symbol": "MNQ1!", "result": "created", "duplicate": False, "http_status": 200, "event_ok": True,
           "event_detail": "created: BUY @ 1", "discord_sent": False, "secret": "should-be-dropped",
           "received_at_api_utc": "2026-10-29T14:00:00+00:00"}
    await env.run(acts.write_audit, rec)
    await env.run(acts.write_audit, rec)
    doc = await mdb.signal_ingest_audit.find_one({"workflow_id": "tv-ingest-aud"})
    assert "secret" not in doc and doc["received_at_et"].startswith("2026-10-29T10:00:00")
    assert await mdb.signal_events.count_documents({}) == 1
