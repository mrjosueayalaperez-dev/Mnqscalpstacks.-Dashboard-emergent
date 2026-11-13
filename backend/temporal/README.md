# Temporal worker (birth cell only) — paper-cut 1: heartbeat

A skeleton worker plus one proof workflow (`HeartbeatWorkflow` → `heartbeat_activity`).
The worker runs as **its own process or container**. `server.py` does not import it, and
nothing on Emergent, Render, or Vercel changes. The activity is a no-op (no Mongo, Yahoo, Discord, or ATI).
Order routing stays disabled.

## Env vars
| Var | Default | Notes |
|---|---|---|
| `TEMPORAL_ADDRESS` | `localhost:7233` | gRPC frontend |
| `TEMPORAL_NAMESPACE` | `default` | |
| `TEMPORAL_TASK_QUEUE` | `mnq-birthcell-main` | |
| `TEMPORAL_TLS` | `false` | `true` enables TLS |
| `TEMPORAL_TLS_CERT_PATH` / `TEMPORAL_TLS_KEY_PATH` | — | optional mTLS client cert/key files |
| `TEMPORAL_API_KEY` | — | optional, Temporal Cloud only |

## Run locally (no Docker: Temporal CLI)
```bash
# 1. Dev server (UI at http://localhost:8233)
temporal server start-dev --db-filename ~/temporal.db
# 2. Worker (Python 3.12)
cd backend && python3.12 -m venv .tvenv && .tvenv/bin/pip install -r temporal/requirements.txt
.tvenv/bin/python -m temporal.worker
# 3. Start one heartbeat
.tvenv/bin/python -m temporal.start_heartbeat manual
# 4. Inspect history (expect WorkflowExecutionCompleted)
temporal workflow show --workflow-id <id printed by step 3>
```
Tests: `pip install pytest pytest-asyncio temporalio && pytest backend/tests/test_temporal_heartbeat.py`.
The time-skipping test server downloads on the first run.

## Run with Docker
```bash
docker compose -f docker-compose.temporal.yml up -d
docker compose -f docker-compose.temporal.yml logs -f worker
docker compose -f docker-compose.temporal.yml exec temporal temporal workflow list
```
Ports are bound to 127.0.0.1. Do not expose 7233 or 8233 publicly. The dev server has no auth.

## Birth cell without Docker (systemd)
Install the CLI from https://temporal.download/cli/archive/latest?platform=linux&arch=amd64 into `/usr/local/bin`.

`/etc/systemd/system/temporal-dev.service`
```ini
[Unit]
Description=Temporal dev server (birth cell)
After=network-online.target
[Service]
User=mnq
ExecStart=/usr/local/bin/temporal server start-dev --ip 127.0.0.1 --db-filename /var/lib/temporal/temporal.db
Restart=always
[Install]
WantedBy=multi-user.target
```
`/etc/systemd/system/mnq-temporal-worker.service`
```ini
[Unit]
Description=MNQ Temporal worker (mnq-birthcell-main)
After=temporal-dev.service
Requires=temporal-dev.service
[Service]
User=mnq
WorkingDirectory=/opt/mnq/backend
Environment=TEMPORAL_ADDRESS=127.0.0.1:7233
Environment=TEMPORAL_NAMESPACE=default
Environment=TEMPORAL_TASK_QUEUE=mnq-birthcell-main
ExecStart=/opt/mnq/backend/.tvenv/bin/python -m temporal.worker
Restart=always
[Install]
WantedBy=multi-user.target
```
`sudo mkdir -p /var/lib/temporal && sudo chown mnq /var/lib/temporal && sudo systemctl daemon-reload && sudo systemctl enable --now temporal-dev mnq-temporal-worker`

## Paper-cut 2: TradingView ingest workflow (`TvIngestWorkflow`)
The API starts this workflow only when `TEMPORAL_ENABLED=true`. It is **off by default**: with it off, both webhook
routes keep their current synchronous path, with the new secret rules applied.

| Var | Where | Default | Notes |
|---|---|---|---|
| `TEMPORAL_ENABLED` | API | `false` | `true` sends HOLD/CLOSE/BUY/SELL through the workflow |
| `SIGNAL_WEBHOOK_SECRET` | API | — | **required**. Unset → 503 on both webhook routes |
| `MONGO_URL`, `DB_NAME` | worker | — / `mnqscalpstacks` | birth-cell worker needs the same Mongo as the API |
| `DISCORD_WEBHOOK_URL` | worker | — | optional. Sending needs the full backend deps (`pip install -r backend/requirements.txt`) |

Secret rules (both `/api/signals/tradingview` and legacy `/api/webhook/tradingview`):
- The secret comes from the `X-Webhook-Secret` header or the JSON body `secret` field. `?secret=` is ignored.
- It is checked with `hmac.compare_digest`.
- Unset → 503 `Webhook disabled: secret not configured`. Wrong or missing → 401.

Flow: route (secret → parse → PRICE stays sync → kill switch at its existing position) → `TvIngestWorkflow`:
`validate_and_price` (non-retryable validation errors; live-price fallback) → `persist_signal` (idempotent per
workflow id via the unique sparse index `signals.ingest_key`) → `notify_discord` (≤5 attempts; the `discord_sent` flag
prevents a second send) → `write_audit` (`signal_ingest_audit`, never stores the secret, plus one `signal_events` line).

Workflow id = `tv-ingest-` + sha256(secret-free normalized payload + TradingView `time`, or the UTC minute when there is no `time`).
A duplicate delivery attaches to the same id and returns the original result: no second insert, no second Discord message.

API responses when enabled:
- Same shapes as today if the workflow finishes within 1.5s.
- Otherwise `202 {"status":"accepted","workflow_id"}`.
- Temporal unreachable → `503 {"detail":"ingest unavailable"}` plus a `signal_events` entry. There is no local fallback.
- Workflow failed after retries → `500 {"detail":"ingest failed","workflow_id"}`.

Birth-cell Mongo: point the worker's `MONGO_URL` at the same database the API uses (Atlas or a local mongod on
birth cell, bound to 127.0.0.1). Signals stay display-only. Nothing here calls ATI, `/trades`, or any order routing.

Futures trading involves substantial risk of loss and is not suitable for all investors. This is education and structured practice, not financial advice. Past performance is not indicative of future results.
