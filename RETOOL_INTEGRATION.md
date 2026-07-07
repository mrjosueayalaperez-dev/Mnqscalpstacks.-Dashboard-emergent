# Retool Integration Guide — MNQ Scalp Stacks API

Retool is the new operator UI. The React frontend at `/operator` still works and stays live for now, but Retool becomes the primary trading terminal.

## Base URL
- **Production:** `https://mnq-scalp-stack.emergent.host`
- **Preview:** `https://mnq-scalp-stack.preview.emergentagent.com`

All endpoints are under `/api/*`.

## OpenAPI Spec (Auto-Import Into Retool)

```
{BASE_URL}/api/openapi.json   ← JSON spec
{BASE_URL}/api/docs           ← Interactive Swagger UI
{BASE_URL}/api/redoc          ← ReDoc alternative
```

**How to import into Retool:**
1. Retool → Resources → **Create new** → **REST API** (or OpenAPI)
2. Base URL: paste production URL above
3. Under **Authentication**: choose "Custom auth" → header name `X-API-Key`, value = your `RETOOL_API_KEY` env value
4. If you use the OpenAPI import path, point it at `{BASE_URL}/api/openapi.json` and it will generate every endpoint as a Retool query stub.

## Authentication

**Reads are OPEN.** Retool dashboards showing state/journal/market data don't need any header.

**Writes require `X-API-Key`.** Every mutating endpoint (`POST /operator/order`, `POST /operator/control/*`) is guarded by the `require_write_key` dependency.

### Enable auth (recommended before shipping Retool to your team)
Set the env var on the backend:
```
RETOOL_API_KEY=<generate a long random string, e.g. `openssl rand -hex 32`>
```
Restart the backend; all writes now require the matching header. Reads stay open.

If `RETOOL_API_KEY` is empty (current state), writes are OPEN — fine for solo development but **do not deploy Retool to teammates without setting it**.

## Endpoints Retool Will Use Most

### Trading cockpit
| Method | Endpoint | Purpose |
|---|---|---|
| GET  | `/api/operator/state`             | Balance, PnL, position, safety gates status |
| POST | `/api/operator/order`             | Submit BUY/SELL/CLOSE/BREAK_EVEN (bracketed) |
| POST | `/api/operator/control/{action}`  | flatten / pause / resume / kill / unkill / reset_session |
| GET  | `/api/operator/journal`           | Paginated order log (supports `limit`, `skip`, `action`, `since`) |
| GET  | `/api/operator/candles`           | OHLCV + EMA/VWAP for a Retool chart component |

### Market data
| Method | Endpoint | Purpose |
|---|---|---|
| GET  | `/api/futures/mnq`     | Live snapshot (real Yahoo NQ=F feed) |
| GET  | `/api/market/context`  | PDH/PDL/ADR/range expansion for daily anchors |
| WS   | `/api/ws/mnq`          | Live tick stream (~3s cadence). Retool supports WS with the WebSocket resource type. |

### Admin
| Method | Endpoint | Purpose |
|---|---|---|
| GET  | `/api/admin/overview`   | KPIs for the ops dashboard |
| GET  | `/api/admin/subscribers`| Paginated Stripe subscribers |
| GET  | `/api/admin/clicks`     | Affiliate revenue breakdown |

## Sample Retool Queries

### Submit an order (button click handler)
```js
// Retool "Query JSON" or "REST API" query
Method: POST
URL: {{ backend_url }}/api/operator/order
Headers: X-API-Key: {{ retool_api_key.value }}
Body (JSON):
{
  "action": "BUY",
  "symbol": "MNQ",
  "qty": 1,
  "order_type": "MARKET",
  "sl_ticks": 40,
  "tp_ticks": 120,
  "preset": "SNIPE_2R"
}
```
Bind: `buyButton.onClick → run(submitBuyOrder)`

### Poll cockpit state every 2s (for the live position card)
```js
Method: GET
URL: {{ backend_url }}/api/operator/state
Run behavior: Interval → 2000ms
Transform (optional):
return {
  price: data.position.avg_entry,
  side: data.position.side || "FLAT",
  ticks: Math.round((data.balance - 100000) / 0.5),
  pnl: data.daily_pnl,
  killed: data.kill_switch,
}
```

### Journal table (Retool Table component)
```js
Method: GET
URL: {{ backend_url }}/api/operator/journal
Params:
  limit: {{ journalTable.pageSize }}
  skip:  {{ journalTable.pagination.offset }}
  action: {{ actionFilter.value }}     // optional
  since:  {{ dateFilter.value.toISOString() }}   // optional
```
Bind `journalTable.data = {{ journalQuery.data.entries }}`.
Bind `journalTable.totalRecords = {{ journalQuery.data.total }}`.

### WebSocket resource for live ticks
Retool → Resources → WebSocket → `wss://{host}/api/ws/mnq`.
No auth headers needed on the WS (read-only). Bind incoming messages to a state variable and drive your price display off it.

## Error Codes You'll See from `/api/operator/order`

| Status | Reason | Retool handling |
|---|---|---|
| 200 | Order accepted | Show success toast |
| 400 | LIMIT requires `limit_price` | Show field error |
| 401 | Missing/invalid `X-API-Key` | Re-check Retool resource auth |
| 423 | Kill switch / paused / max loss / max trades | Show blocking toast, disable order buttons |
| 429 | 1500ms cooldown not elapsed | Show cooldown countdown |
| 503 | Live MNQ feed offline | Show "market data unavailable" banner |

The `detail` field always contains a human-readable explanation.

## Env Vars Cheatsheet

Add these to `backend/.env`:
```
RETOOL_API_KEY=<long random string>          # Required to lock writes
AFFILIATE_URL_NINJATRADER=...                # Already there
AFFILIATE_URL_TRADINGVIEW=...
```

Then `sudo supervisorctl restart backend` (preview) or redeploy (production).

## NinjaTrader Bridge (Phase 2 — Coming)

When we wire the NinjaTrader ATI file writer, the `/api/operator/order` endpoint stays identical — Retool doesn't change. The backend just gains the ability to emit real order files instead of just logging. Zero client changes required.
