# Practice-alert notifications (PR A)

Discord is the only outbound channel in this repo. This module (`backend/notifications.py`) makes delivery reliable without exposing secrets.

- Config status is a boolean only (`discord_configured`). The webhook URL is never returned, logged, or stored in delivery rows.
- Josue sets `DISCORD_WEBHOOK_URL` himself. A missing or placeholder value (`REPLACE_WITH_YOUR_DISCORD_WEBHOOK_URL`) is treated as unconfigured.
- Delivery retries with exponential backoff. Exhausted attempts persist `status: failed` plus `last_error` and `attempts` in Mongo `alert_deliveries` (or the in-memory store in tests).
- Duplicates are skipped when the same `alert_key` (strategy + instrument + timeframe + direction + trigger) was delivered or is pending inside `ALERT_DEDUP_WINDOW_SECONDS` (default 180).
- Stale-data guard: a quote older than the expected Yahoo delay (10 minutes) plus a 5-minute grace window is not sent.
- Data labels: `delayed` (Yahoo, always), `simulated`, `paper`, or `live` (only a licensed TradingView real-time tape). Alerts never imply that a trade was placed.
- User-facing copy includes the verbatim futures disclaimer and never describes candle delta as order flow.

Safe tests use a mock HTTP post and a fake webhook URL (`https://example.invalid/...`). Do not point tests at a real Discord webhook or production.

## Alert identity and dedup retention

- **Identity (`alert_key`):** the first 24 hex characters of SHA-256 over `strategy|instrument|timeframe|direction|trigger` (fields normalized for case/whitespace), with two extra segments appended when the caller supplies them: `source=<feed source>` and `ts=<event timestamp>`. The configured-alert engine (`_emit_practice_alert` in `server.py`) always sets the key explicitly, using the snapshot's feed source and the last bar's time (ISO 8601) as the event timestamp — so re-evaluating the same bar dedups, while a new bar is a distinct event. When a payload arrives without an `alert_key`, `deliver_discord` derives the same key from the payload fields (including `source`/`data_source` and the `as_of`/`timestamp` value).
- **Window:** a key that was claimed inside `ALERT_DEDUP_WINDOW_SECONDS` (default 180) occupies the slot; a later delivery of the same key is recorded as `skipped_duplicate` and is not posted again.
- **Claim retention:** claims live in the Mongo `alert_delivery_claims` collection, one document per `alert_key` (the key is the document `_id`). Claim documents are not deleted when the window lapses — the next delivery after the window reuses the same document with a compare-and-set on `claimed_at`, so exactly one claim row per alert identity persists. Individual delivery attempts are kept separately as append-only history in `alert_deliveries`.
