# P0 hardening — environment variables (names only, never commit values)

| Variable | Purpose | Unset behaviour |
|---|---|---|
| `RETOOL_API_KEY` | `X-API-Key` for every mutating endpoint guarded by `require_write_key` | **Fails closed**: 503 on all guarded writes |
| `SIGNAL_WEBHOOK_SECRET` | `X-Webhook-Secret` header for `/api/signals/tradingview` and `/api/webhook/tradingview` | **Rejected**: 503; query-param and JSON-body secrets are never accepted |
| `TV_DATA_MODE` | `delayed` (default) or `realtime`. Labels the TradingView webhook price tape: `DELAYED 10m` vs `REAL-TIME`. Set `realtime` only if the TradingView data tier is licensed real-time for CME. | `delayed` |

Yahoo (`yahoo:NQ=F`) is always labelled `DELAYED 10m` regardless of `TV_DATA_MODE`.

Ingest: the secured TradingView webhook (`POST /api/signals/tradingview`) is the only signal/price ingest.
Signals are display-only, tagged `PAPER`. Broker routing (NinjaTrader ATI) is hard-disabled; Tradovate is untouched.
`GET /api/market/data-mode` exposes the current mode for the UI.
