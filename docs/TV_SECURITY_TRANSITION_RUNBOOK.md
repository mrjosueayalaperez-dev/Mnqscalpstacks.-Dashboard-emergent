# TradingView signal security: transition runbook + pre-deploy gate

Status: **DRAFT, documentation only.** Nothing in this doc has been executed. No merges, deploys or env changes
without Claude review and Josue's sign-off. Josue sets and rotates every secret himself, while parked.
**Never** paste a real secret into GitHub, chat, logs, client-side code or this doc.
**Never** put a secret in a variable named `REACT_APP_*` — those are baked into the public browser bundle.

Times are America/New_York (ET).

## 1. Overview and principles

**Current intended flow (PR #15 — Vercel validates, then forwards to Emergent):**

```
TradingView alert
  → POST https://mnqscalpstacks.com/api/signals/tradingview
     (Vercel serverless: frontend/api/signals/tradingview.js)
  → validates SIGNAL_WEBHOOK_SECRET server-side
     (JSON body `secret` or `x-webhook-secret` header)
  → on success, swaps in EMERGENT_WEBHOOK_SECRET and forwards
     server-side to https://mnq-scalp-stack.emergent.host/api/signals/tradingview
  → Emergent backend is the single code path: kill switch, per-action
     semantics (BUY/SELL cards, HOLD log-only, CLOSE expiry, PRICE tape),
     and the database write the dashboard reads
  → Vercel returns the Emergent status and JSON unchanged
     (502 `upstream_unreachable` if Emergent cannot be reached; never a false 200)
```

This replaces the earlier (Oct 29) plan in which TradingView posted **directly** to the Emergent
webhook URL as the primary production path. Direct posts to Emergent remain the **temporary**
state until Josue switches the TradingView webhook URL, and they remain the rollback path.

**Until PR #15 is merged, both Vercel env vars are set, a preview check has passed, and Josue
switches the alerts, TradingView must stay pointed at Emergent.** Phase 1 on `main` (`b439c02`)
is a Vercel validate-and-log receiver only; it does not write to the dashboard database.
PR #15 is the forwarder. PR #12 hardens the Emergent-side contract that PR #15 forwards into.

Vercel-side responses (from the receiver itself):
- `503` `secret_not_configured` — `SIGNAL_WEBHOOK_SECRET` unset on Vercel
- `401` `bad_or_missing_secret` — wrong or missing TradingView secret
- `503` `upstream_not_configured` — `EMERGENT_WEBHOOK_SECRET` unset on Vercel
- `502` `upstream_unreachable` — Emergent not reachable
- otherwise, Emergent's status and JSON are passed through

Emergent-side contract (PR #12, the forward target):
- `SIGNAL_WEBHOOK_SECRET` unset → `503` on both `/api/signals/tradingview` (primary) and `/api/webhook/tradingview` (legacy)
- Secret accepted from the JSON body `secret` field (what PR #15 sends) **or** the `X-Webhook-Secret` header. `?secret=` in the URL is **ignored**.
- Wrong or missing secret → `401`. Comparison is constant-time.
- `GET /api/signals/receiver-status` shows `secret_configured` + `secret_masked: "********"`, never the raw value.
- `TEMPORAL_ENABLED` stays OFF on Emergent. Emergent cannot run a Temporal worker. With it off, the existing synchronous ingest path runs unchanged apart from the secret rules.

**Unchanged:** signals stay display-only; ATI and order routing stay disabled; TEST/PAPER/LIVE labels, risk disclaimers and kill-switch behavior are unchanged. This route must not label a card LIVE in a way that implies a real trade.

Principles:
- Minimize the signal gap by doing rotation and alert updates back-to-back.
- Every step can be rolled back (point TradingView back at Emergent).
- Verify with evidence before calling it done.
- Josue sets and rotates secrets himself. No agent reads, prints or pastes them.

## 2. Preconditions (all must be true)
- [ ] Claude security review done, and Josue has signed off on PR #15 (forwarder), PR #11 and PR #12 (and on #9 if it ships in the same redeploy).
- [ ] PRs merged in the agreed order. #12 stays stacked on #11 until #11 is merged; then retarget #12 to `main`. #15 does not edit Emergent backend files.
- [ ] Josue is **parked** (not trading) and has 30–45 min free.
- [ ] Josue has generated the **new Vercel** secret himself (e.g. a password manager, or `openssl rand -hex 32` on his own machine) and keeps it out of chat and repos.
- [ ] Josue has a list of every TradingView alert that will post to the Vercel URL (URL + message).
- [ ] The pre-deploy gate (section 4) is all checked.
- [ ] A preview (or live Vercel) check has confirmed: POST returns JSON not HTML; the secret is server-only `SIGNAL_WEBHOOK_SECRET` (never `REACT_APP_*`); a forwarded HOLD appears in the same database the dashboard reads; cards are not labeled LIVE as if they were real trades.

## 3. Ordered steps
| # | Step | Who |
|---|---|---|
| 0 | Note the current Emergent deployment and the current TradingView webhook URLs, so rollback has a target | Josue |
| a | Set Vercel server-only env: `SIGNAL_WEBHOOK_SECRET` (new) and `EMERGENT_WEBHOOK_SECRET` (current Emergent value, copied by Josue from Emergent — never through chat) | Josue |
| b | Confirm Emergent `SIGNAL_WEBHOOK_SECRET` is still set (the forward target). Redeploy Emergent only if PR #12 (fail-closed secret) is also shipping | Josue |
| c | Update every TradingView alert webhook URL and message, **immediately** after (a) is live | Josue |
| d | Leave `TEMPORAL_ENABLED` unset/OFF on Emergent | Josue (no action) |
| e | Run the verification checks | Josue / eng |
| f | Roll back if any check fails | Josue |

### (a) Vercel secrets (server-only)
- In the Vercel project for mnqscalpstacks.com, set:
  - `SIGNAL_WEBHOOK_SECRET` — the **new** secret TradingView will send to Vercel after the switch.
  - `EMERGENT_WEBHOOK_SECRET` — the **current** secret the Emergent backend already expects. Josue copies it from Emergent's Secrets UI himself.
- Both are server-only environment variables. **Do not** name them `REACT_APP_*`. **Do not** put them in frontend code, a committed `.env`, or chat.
- Saving a Vercel env var does not always attach to an existing deployment; Josue should confirm the deployment that will receive TradingView traffic has both variables.
- Do not leave `SIGNAL_WEBHOOK_SECRET` unset on Vercel. Unset means every alert gets `503 secret_not_configured`.
- Do not leave `EMERGENT_WEBHOOK_SECRET` unset. Unset means a valid TradingView post gets `503 upstream_not_configured` and is not forwarded.

### (b) Emergent secret (forward target)
- The Emergent backend still authenticates the forwarded request with its own `SIGNAL_WEBHOOK_SECRET`.
- If that value changes, Josue must update `EMERGENT_WEBHOOK_SECRET` on Vercel in the same window, or forwards will get `401`.
- If PR #12 ships: an unset Emergent secret means every forwarded alert gets `503`. Do not leave it unset.

### (c) Update each TradingView alert
For each alert:
1. **Webhook URL:** `https://mnqscalpstacks.com/api/signals/tradingview` only (port 443). Remove any Emergent host and any `?secret=...`.
2. **Message:** JSON with a `"secret"` field set to the **Vercel** `SIGNAL_WEBHOOK_SECRET` (not the Emergent value). Leave the rest of the message the same.

Template (the placeholder only, never a real value here):
```json
{
  "secret": "<PASTE VERCEL SIGNAL_WEBHOOK_SECRET HERE>",
  "action": "{{strategy.order.action}}",
  "symbol": "MNQ1!",
  "interval": "{{interval}}",
  "price": "{{close}}",
  "time": "{{timenow}}",
  "source": "MNQ Scalp Punch v1"
}
```
- **Plain-text alerts** (e.g. `BUY MNQ1! 29917.25`) can't carry a body secret. Convert them to the JSON form above, because TradingView generally can't send custom headers (general knowledge, not verified).
- **Do not** point new alerts at `/api/webhook/tradingview` (legacy, and not the Vercel route).
- **Do not** switch TradingView until the four-point check in the preconditions has passed.

### (d) Temporal
Leave `TEMPORAL_ENABLED` unset (OFF) on Emergent. Turn it on only when the founder says so, and only once a Temporal server **and** worker run on birth cell.

### (e) Verification (after the switch)
Use a **test** request, not a live alert, during RTH. Never paste the real secret into shared logs. Expected results against the **Vercel** URL:
| Check | Expected |
|---|---|
| Valid Vercel secret in JSON body, `action: "HOLD"` (records nothing tradeable) | 200, Emergent body "HOLD accepted — no order placed."; the HOLD is visible in the dashboard feed |
| Wrong secret | 401 from Vercel (`bad_or_missing_secret`) — nothing forwarded |
| No secret | 401. If you get 503 `secret_not_configured`, the Vercel env is missing → go to (f) or fix the env |
| Secret only in `?secret=` | 401 (Vercel and Emergent both ignore query-string secrets) |
| `GET` on the Vercel route | JSON health: `receiver: "vercel"`, `mode: "forward"`, `secret_configured` / `upstream_configured` booleans, never the raw values |
| Emergent down | 502 `upstream_unreachable`, never a false 200 |
| `GET https://mnq-scalp-stack.emergent.host/api/signals/receiver-status` | `secret_configured: true`, `secret_masked: "********"`, raw secret absent |
| One real TradingView alert fires | Appears in the Signals tab via the Emergent database; "last success" updates. The card must not be labeled LIVE in a way that implies a real trade. |

### (f) Rollback
1. In TradingView, restore the previous webhook URL (`https://mnq-scalp-stack.emergent.host/api/signals/tradingview`) and the previous message, including the Emergent secret in the body if that is what the alerts used.
2. If an Emergent deploy was part of this change, roll back to the deployment noted in step 0 and restore the previous Emergent `SIGNAL_WEBHOOK_SECRET` privately.
3. Keep `TEMPORAL_ENABLED` OFF.
4. Re-check that one alert lands on the Emergent path.

## Risks and timing
- **Signal gap:** from the moment the TradingView URL or secret changes until each alert is updated, alerts fail with 401. Minimize it by doing this while parked, outside RTH if possible.
- **TradingView retries:** whether TradingView retries a failed webhook is **unknown**. Assume any alert that fails during the window is lost.
- **Plain-text alerts:** they need converting to JSON (see (c)).
- **Two secrets:** the Vercel secret and the Emergent secret are different values. Mixing them up means either Vercel 401s the alert or Emergent 401s the forward.
- **Emergent dependency:** PR #15 is a bridge, not the migration. If Emergent is down, Vercel returns 502 and no card is written.
- **Phase 1 already on `main`:** the live Vercel route today may still be validate-and-log until #15 is merged. Switching TradingView before #15 ships would log alerts on Vercel without writing them to the dashboard database.
- **Leak exposure:** the old Emergent secret was readable through `receiver-status` before #12, so Emergent-side rotation is required, not optional, when #12 ships.
- **Redeploy side effects:** other PRs ship with an Emergent redeploy (see the gate below).

## Owners and contacts
- **Josue Ayala-Perez:** owner of TradingView alerts, Vercel and Emergent env, deploys, rollback, and final sign-off.
- **Claude:** security review before merge.
- **Eng (Grok Bot):** code, docs and local evidence only. No production access is used, and no secret is read or printed.

## 4. Pre-deploy gate
Check every box before switching TradingView or redeploying. Unknowns are marked; resolve them before going live.

**Env vars — Vercel (server-only)**
- [ ] `SIGNAL_WEBHOOK_SECRET`: **must be set** to the new value TradingView will send. Unset means every alert gets 503. Never a `REACT_APP_*` name.
- [ ] `EMERGENT_WEBHOOK_SECRET`: **must be set** to the current Emergent webhook secret (founder pastes from Emergent). Unset means 503 `upstream_not_configured`.

**Env vars — Emergent**
- [ ] `SIGNAL_WEBHOOK_SECRET`: **must be set** (the forward target). Unset means every forwarded alert gets 503 once #12 is live.
- [ ] `RETOOL_API_KEY` (PR #9, if #9 ships):
  - #9 guards the 5 `/api/admin/*` routes (`overview`, `subscribers`, `subscribers/{id}/tier`, `DELETE subscribers/{id}`, `clicks`).
  - It allows either a matching `X-API-Key` (accepted **only if** `RETOOL_API_KEY` is non-empty; constant-time) **or** a logged-in session with `role == "admin"`.
  - **If unset:** API keys are never accepted. Retool panels calling `/api/admin/*` with `X-API-Key` (see `RETOOL_INTEGRATION.md`) get **401/403**. AdminPanel in the app still works for an admin session.
  - **If set:** Retool must send the same value.
  - #9 does **not** change `require_write_key`. On `main` that's still a no-op when the key is unset, so writes stay open. PR #6 would make it fail closed with 503.
- [ ] `TEMPORAL_ENABLED`: unset/false. The other `TEMPORAL_*` vars are irrelevant on Emergent.
- [ ] `MONGO_URL` and `DB_NAME`: unchanged.
- [ ] `JWT_SECRET`, `DISCORD_WEBHOOK_URL`, LLM/Stripe keys: unchanged. Confirm they're present.

**Redeploy / switch scope**
- Vercel already serves the site at mnqscalpstacks.com. The Phase 1 receiver (`b439c02` on `main`) is validate-and-log only. The database-writing path is still Emergent, via PR #15's forwarder once that PR is merged.
- **Unknown which commit Emergent serves now.** Its deploy history isn't visible from the repo. Everything merged after `58bf4c8` (2026-09-28 08:17 ET) may not be live yet and would ship together on an Emergent redeploy:
  - #1 (frontend deps)
  - Render/Atlas docs and the `emergentintegrations` shim (`c77ac62`)
  - #2 (copilot security)
  - #3 (honesty labels)
  - #4 (chart counter)
  - #5 (Apex P&L journal)
  - #8 (checklist auth, `b756955`): checklist now **requires login**
  - homepage claim removal (`9c7c05b`, founder-approved Nov 10)
  - then #11, #12, and #9 if approved
- [ ] Josue confirms in Emergent which commit is currently deployed, then reviews this list.
- [ ] Note especially `c77ac62`, which replaces Emergent's private `emergentintegrations` with a local shim. Confirm it works on Emergent's image before relying on it.
- [ ] Do not switch TradingView until PR #15 (or the approved forwarder) is live and the four-point check has passed.

**Credits and cost**
- [ ] Emergent redeploys are manual and may consume credits. Josue decides when.
- [ ] Vercel env changes are founder-only.

**Rollback**
- [ ] The previous Emergent deployment is noted, and Emergent rollback is available (see 3(f)).
- [ ] The previous TradingView URLs and secrets are recorded privately by Josue, so alerts can be pointed back at Emergent.

Futures trading involves substantial risk of loss and is not suitable for all investors. This is education and structured practice, not financial advice. Past performance is not indicative of future results.
