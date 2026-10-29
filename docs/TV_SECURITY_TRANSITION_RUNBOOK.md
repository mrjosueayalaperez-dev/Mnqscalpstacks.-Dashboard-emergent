# TradingView signal security: transition runbook + pre-deploy gate

Status: **DRAFT, documentation only.** Nothing in this doc has been executed. No merges, deploys or Emergent changes
without Claude review and Josue's sign-off. Josue makes all TradingView and Emergent env changes himself, while parked.
**Never** paste a real secret into GitHub, chat, logs or this doc.

Times are America/New_York (ET).

## 1. Overview and principles
After this change, TradingView webhooks are accepted only with a valid secret:
- **Final contract** (PR #12; reconciled with PR #6, see the comment on #12):
  - `SIGNAL_WEBHOOK_SECRET` unset → `503 Webhook disabled: secret not configured` on **both** webhook routes.
  - The secret is accepted from the `X-Webhook-Secret` header **or** the JSON body `secret` field. `?secret=` in the URL is **ignored**, so a query-only secret gets 401.
  - Wrong or missing secret → 401. The comparison is constant-time.
  - `GET /api/signals/receiver-status` shows `secret_configured` + `secret_masked: "********"`, never the raw value.
- **Routes:** `POST /api/signals/tradingview` (primary) and `POST /api/webhook/tradingview` (legacy). Both now require the secret.
- **`TEMPORAL_ENABLED` stays OFF on Emergent.** Emergent cannot run a Temporal worker. With it off, the existing synchronous ingest path runs unchanged apart from the secret rules.
- **Unchanged:** signals stay display-only; ATI and order routing stay disabled; TEST/PAPER/LIVE labels, risk disclaimers and kill-switch behavior are unchanged.

Principles:
- Minimize the signal gap by doing rotation and alert updates back-to-back.
- Every step can be rolled back.
- Verify with evidence before calling it done.

## 2. Preconditions (all must be true)
- [ ] Claude security review done, and Josue has signed off on PR #11 and PR #12 (and on #9 if it ships in the same redeploy).
- [ ] PRs merged in order: #11 → retarget #12 to `main` → #12. #6 is rebased later (see the reconciliation note on #12).
- [ ] Josue is **parked** (not trading) and has 30–45 min free.
- [ ] Josue has generated a new secret himself (e.g. a password manager, or `openssl rand -hex 32` on his own machine) and keeps it out of chat and repos.
- [ ] Josue has a list of every TradingView alert that posts to this backend (URL + message).
- [ ] The pre-deploy gate (section 4) is all checked.

## 3. Ordered steps
| # | Step | Who |
|---|---|---|
| 0 | Note the current Emergent deployment, so rollback has a target | Josue |
| a | Rotate `SIGNAL_WEBHOOK_SECRET` server-side (Emergent env) and redeploy `main` | Josue |
| b | Update every TradingView alert, **immediately** after (a) | Josue |
| c | Leave `TEMPORAL_ENABLED` unset/OFF on Emergent | Josue (no action) |
| d | Run the verification checks | Josue / eng |
| e | Roll back if any check fails | Josue |

### (a) Rotate the secret on Emergent
- Set `SIGNAL_WEBHOOK_SECRET=<new value>` in Emergent's environment, then redeploy the reviewed `main`.
- **The old secret stops working immediately.** Every alert fails with 401 until (b) is done, so do (a) and (b) back-to-back while parked.
- Do not leave the secret unset. Unset means **every** alert gets 503.

### (b) Update each TradingView alert
For each alert:
1. **Webhook URL:** remove any `?secret=...`. The URL becomes exactly `https://<backend-host>/api/signals/tradingview`.
2. **Message:** add a `"secret"` field to the JSON body. Leave everything else in the message the same.

Template (the placeholder only, never a real value here):
```json
{
  "secret": "<PASTE SECRET HERE>",
  "action": "{{strategy.order.action}}",
  "symbol": "MNQ1!",
  "interval": "{{interval}}",
  "price": "{{close}}",
  "time": "{{timenow}}",
  "source": "MNQ Scalp Punch v1"
}
```
- **Plain-text alerts** (e.g. `BUY MNQ1! 29917.25`) can't carry a body secret. Convert them to the JSON form above, because TradingView generally can't send custom headers (general knowledge, not verified).
- **Alerts using the legacy route** `/api/webhook/tradingview`: add `"secret"` to their JSON body too, or move them to the primary URL.

### (c) Temporal
Leave `TEMPORAL_ENABLED` unset (OFF) on Emergent. Turn it on only when the founder says so, and only once a Temporal server **and** worker run on birth cell.

### (d) Verification (after deploy)
Use a **test** request, not a live alert, during RTH. Never paste the real secret into shared logs. Expected results:
| Check | Expected |
|---|---|
| Valid secret in JSON body, `action: "HOLD"` (records nothing tradeable) | 200, "HOLD accepted — no order placed." |
| Wrong secret | 401 |
| No secret | 401. If you get 503, the secret isn't set on the server → go to (e) or fix the env |
| Secret only in `?secret=` | 401 |
| The same BUY alert twice within 3 minutes | 2nd response `{"status":"duplicate",...}`; only one signal on the dashboard |
| `GET /api/signals/receiver-status` | `secret_configured: true`, `secret_masked: "********"`, raw secret absent |
| One real TradingView alert fires | Appears in the Signals tab; "last success" updates |

### (e) Rollback
1. In Emergent, roll back to the deployment noted in step 0.
2. Josue restores the previous `SIGNAL_WEBHOOK_SECRET` value and the previous alert URLs and messages, including `?secret=` if they used it before.
3. Keep `TEMPORAL_ENABLED` OFF.
4. Re-check that one alert lands.

## Risks and timing
- **Signal gap:** from (a) until each alert is updated in (b), alerts fail with 401. Minimize it by doing this while parked, outside RTH if possible.
- **TradingView retries:** whether TradingView retries a failed webhook is **unknown**. Assume any alert that fails during the window is lost.
- **Plain-text alerts:** they need converting to JSON (see (b)).
- **Leak exposure:** the old secret was readable through `receiver-status` before #12, so rotation is required, not optional.
- **Redeploy side effects:** other PRs ship with the redeploy (see the gate below).

## Owners and contacts
- **Josue Ayala-Perez:** owner of TradingView alerts, Emergent env and deploys, rollback, and final sign-off.
- **Claude:** security review before merge.
- **Eng (Grok Bot):** code, docs and local evidence only. No production access is used.

## 4. Pre-deploy gate (Emergent)
Check every box before redeploying. Unknowns are marked; resolve them before going live.

**Env vars**
- [ ] `SIGNAL_WEBHOOK_SECRET`: **must be set** to the new value. Unset means every alert gets 503.
- [ ] `RETOOL_API_KEY` (PR #9, if #9 ships):
  - #9 guards the 5 `/api/admin/*` routes (`overview`, `subscribers`, `subscribers/{id}/tier`, `DELETE subscribers/{id}`, `clicks`).
  - It allows either a matching `X-API-Key` (accepted **only if** `RETOOL_API_KEY` is non-empty; constant-time) **or** a logged-in session with `role == "admin"`.
  - **If unset:** API keys are never accepted. Retool panels calling `/api/admin/*` with `X-API-Key` (see `RETOOL_INTEGRATION.md`) get **401/403**. AdminPanel in the app still works for an admin session.
  - **If set:** Retool must send the same value.
  - #9 does **not** change `require_write_key`. On `main` that's still a no-op when the key is unset, so writes stay open. PR #6 would make it fail closed with 503.
- [ ] `TEMPORAL_ENABLED`: unset/false. The other `TEMPORAL_*` vars are irrelevant on Emergent.
- [ ] `MONGO_URL` and `DB_NAME`: unchanged.
- [ ] `JWT_SECRET`, `DISCORD_WEBHOOK_URL`, LLM/Stripe keys: unchanged. Confirm they're present.

**Redeploy scope (what ships from `main`)**
- The last Emergent-agent commit on `main` is `58bf4c8` (2026-09-28 08:17 ET).
- **Unknown which commit Emergent serves now.** Its deploy history isn't visible from the repo. Everything merged after `58bf4c8` may not be live yet and would ship together:
  - #1 (frontend deps)
  - Render/Atlas docs and the `emergentintegrations` shim (`c77ac62`)
  - #2 (copilot security)
  - #3 (honesty labels)
  - #4 (chart counter)
  - #5 (Apex P&L journal)
  - #8 (checklist auth, `b756955`): checklist now **requires login**
  - then #11, #12, and #9 if approved
- [ ] Josue confirms in Emergent which commit is currently deployed, then reviews this list.
- [ ] Note especially `c77ac62`, which replaces Emergent's private `emergentintegrations` with a local shim. Confirm it works on Emergent's image before relying on it.

**Credits and cost**
- [ ] Emergent redeploys are manual and may consume credits. Josue decides when.

**Rollback**
- [ ] The previous deployment is noted, and Emergent rollback is available (see 3(e)).
- [ ] The previous secret and alert setup are recorded privately by Josue.

Futures trading involves substantial risk of loss and is not suitable for all investors. This is education and structured practice, not financial advice. Past performance is not indicative of future results.
