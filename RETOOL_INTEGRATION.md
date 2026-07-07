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

## NinjaTrader Bridge (Phase 2 — LIVE)

Phase 2 is shipped. `/api/operator/order` stays identical for Retool — but when ATI
routing is armed, the backend also enqueues a real NinjaTrader OIF command.

### ATI endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET  | `/api/ati/status` | none | enabled flag, bridge heartbeat, queue depth |
| POST | `/api/ati/config` | X-API-Key | `{enabled, account, instrument, atm_template}` |
| GET  | `/api/ati/commands` | X-API-Key | pending OIF commands (bridge polls this) |
| POST | `/api/ati/ack` | X-API-Key | `{command_ids: [...]}` → mark dispatched |
| POST | `/api/ati/heartbeat` | X-API-Key | bridge liveness ping |
| GET  | `/api/ati/bridge-script` | none | download the Windows bridge (`mnq_ati_bridge.py`) |

### Bridge setup (on your trading PC)
1. Download `mnq_ati_bridge.py` from `/api/ati/bridge-script`.
2. NinjaTrader 8 → Tools → Options → Automated trading interface → enable **AT Interface**. Restart NT8.
3. Create ATM templates named exactly `SNIPE_1R`, `SNIPE_2R`, `RUNNER` (matching cockpit presets).
4. `set SCALP_BACKEND_URL=https://<your-app>` and `set SCALP_API_KEY=<RETOOL_API_KEY>` then `python mnq_ati_bridge.py`.
5. Arm **LIVE ROUTING** in the cockpit's ATI panel (or POST `/api/ati/config {"enabled": true}`).
6. Test on **Sim101** before switching the account to live.

## Ready-To-Paste Retool Query Pack

Create a REST resource `MNQ_API` (base URL + `X-API-Key` header), then add:

### 1. `getAtiStatus` — GET `/api/ati/status` (run every 5s)
Bind a Status indicator: `{{ getAtiStatus.data.bridge_online ? "BRIDGE ONLINE" : "OFFLINE" }}`

### 2. `armLiveRouting` — POST `/api/ati/config`
Body: `{ "enabled": {{ !getAtiStatus.data.enabled }} }` — wire to a toggle button.

### 3. `getOperatorState` — GET `/api/operator/state` (run every 2s)
Position card: `{{ getOperatorState.data.position.side || "FLAT" }}`, PnL: `{{ getOperatorState.data.daily_pnl }}`

### 4. `submitOrder` — POST `/api/operator/order`
Body:
```json
{ "action": "{{ sideSelect.value }}", "qty": {{ qtyInput.value }}, "order_type": "MARKET",
  "preset": "{{ presetSelect.value }}", "sl_ticks": 40, "tp_ticks": 120 }
```

### 5. `flattenAll` — POST `/api/operator/control/flatten` (red button + confirm modal)

### 6. `getJournal` — GET `/api/operator/journal?limit=50` → Table on `{{ getJournal.data.entries }}`

### 7. `getClicks` — GET `/api/admin/clicks` → revenue dashboard (`by_partner` bar chart)

### 8. `getSubscribers` — GET `/api/admin/subscribers` → business KPI table

### 9. `getAtiQueue` — GET `/api/ati/commands` → ops table for stuck commands (pending > 60s = bridge down)
