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
