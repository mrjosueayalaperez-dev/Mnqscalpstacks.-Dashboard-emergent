# Moving the backend off Emergent (future-use runbook)

**Status: future use. Do not execute this cut-over now.**

Josue is staying on Emergent for now. This document, the copy script, and the
default-preserving receiver change prepare the later move. They do not change
live traffic, do not republish Emergent, and do not switch TradingView.

Base of this branch: `main` at `a1e5bf5` (PRs #17 and #18 already merged).

Nothing here should be run against production from chat or a shared agent box.
Josue sets every secret and connection string himself and never pastes them
into chat, git, or client-side `REACT_APP_` variables.

---

## Founder-only steps (summary)

These are yours to do when you decide to move. No one else should handle the
values.

1. Stay on Emergent until you choose a move date. No production change is
   required today.
2. In MongoDB Atlas (you already have an account): create or pick a free M0
   cluster, add a database user, and set network access. Copy the connection
   string into a password manager — never into chat.
3. Copy the **names** of the current Emergent env vars into this checklist,
   and privately copy their values from Emergent's env panel into the same
   password manager. Note the production `DB_NAME`.
4. Get a production data export (mongodump, this repo's copy script, or an
   Emergent support dump). Preview-pod data is not production.
5. Run `scripts/migrate_mongo.py` on your own machine: dry-run first, then
   `--apply`. Compare the printed counts.
6. Create the Render web service from the existing `render.yaml`
   (`autoDeploy: false`). Railway is the alternative. Check current pricing
   on the provider's site before you add a card.
7. Enter every env var on the new host yourself (names in §4). Leave
   `TEMPORAL_ENABLED` unset or `false`. Leave
   `STRATEGY_A_PARAMETERS_APPROVED` and `STRATEGY_B_PARAMETERS_APPROVED`
   unset until those parameters are approved.
8. Smoke-test the new backend while the frontend still points at Emergent.
9. Point Vercel `REACT_APP_BACKEND_URL` at the new host and redeploy the
   frontend. Set the server-only `UPSTREAM_WEBHOOK_URL` on the Vercel
   receiver only when you are ready; until then it keeps forwarding to
   Emergent.
10. Do **not** switch TradingView until the 4-point check passes and you
    approve that switch.
11. Keep Emergent running until the new host is verified. Only you cancel
    Emergent later.

This pull request stays a draft until you approve a merge. Merging later
deploys the receiver change to Vercel, but the Emergent URL remains the
default, so live forwarding does not change until you set
`UPSTREAM_WEBHOOK_URL`.

---

## 1. What is moving, and what already lives elsewhere

| Piece | Today | Later target |
|---|---|---|
| Frontend (CRA) | Vercel: `mnqscalpstacks.com` and `mnqscalpstacks-dashboard-emergent.vercel.app` | Same Vercel project; only `REACT_APP_BACKEND_URL` changes |
| TradingView receiver | Vercel `/api/signals/tradingview` (PR #15). Validates `SIGNAL_WEBHOOK_SECRET`, then forwards with `EMERGENT_WEBHOOK_SECRET` | Same route. A new server-only `UPSTREAM_WEBHOOK_URL` is added in this PR; the default stays `https://mnq-scalp-stack.emergent.host/api/signals/tradingview` |
| Backend (FastAPI, Mongo, login, signals, alert engine) | Emergent: `https://mnq-scalp-stack.emergent.host/api`. The live process does **not** auto-update from GitHub. Republish is manual. | Render web service from `render.yaml` (`autoDeploy: false`). Railway is the alternative. |
| Database | Emergent-managed Mongo | MongoDB Atlas M0 (free tier). You already have an Atlas account. |

The reason to move later: GitHub `main` can deploy to a host you control,
with no manual Emergent republish.

Known constraint: Emergent Google login (`auth.emergentagent.com`) may break
if the Emergent app is cancelled. Email/password JWT login already works.
Replacing Google login is a follow-up, not part of this PR.

---

## 2. Atlas M0 cluster, database user, and network access

You do these in [MongoDB Atlas](https://cloud.mongodb.com). An agent should
never handle, read, or print the connection string.

1. Create a project if you need one, then create a **Free M0** cluster.
   AWS `us-east-1` (N. Virginia) matches Render's Virginia region.
2. Database Access → add a user with `readWrite` on the target database.
   Use a generated password.
3. Network Access:
   - Render Starter has no static egress IP, so Atlas usually needs
     `0.0.0.0/0` for the backend to connect. Prefer tightening this later
     if the host offers a static IP.
   - If you run the copy script from your own computer first, also allow
     your current IP.
4. Connect → Drivers → copy the `mongodb+srv://…` string. That value is
   `MONGO_URL` (and, for the copy script, `TARGET_MONGO_URL`). Store it
   privately. Do not paste it into chat, GitHub, or Vercel client env vars.

Note the database name you will use. It must match `DB_NAME` on the new
host. If you keep the Emergent production name, sessions and existing
documents line up cleanly.

---

## 3. Exporting the data from Emergent's Mongo

Production data lives in Emergent's managed Mongo for the **deployed** app.
The preview pod's database is not production (users, payments, and proofs
differ). Record per-collection counts before and after any copy.

### Option A — `mongodump` / `mongorestore` (you run this)

If Emergent's env panel gives you the production `MONGO_URL` and `DB_NAME`,
on a machine with [MongoDB Database Tools](https://www.mongodb.com/docs/database-tools/):

```bash
# Values stay in your shell environment. Do not paste them into chat.
mongodump --uri "$EMERGENT_MONGO_URL" --db "$EMERGENT_DB_NAME"   --gzip --archive=mnq-prod.archive.gz

mongorestore --uri "$ATLAS_MONGO_URL" --gzip --archive=mnq-prod.archive.gz   --nsInclude "$EMERGENT_DB_NAME.*"
```

To restore into a different database name, use `--nsFrom` / `--nsTo` and
set `DB_NAME` on the new host to that name.

Delete the local archive afterwards. It contains emails and password hashes.

### Option B — `scripts/migrate_mongo.py` (preferred when you have both URIs)

This script is in this PR. It reads `SOURCE_MONGO_URL` and
`TARGET_MONGO_URL` from the environment only (never as command-line flags).
It never prints URLs or passwords.

- Dry-run is the default: counts only, no writes.
- `--apply` upserts each document by `_id` (safe to re-run).
- It prints a per-collection count comparison (`source`, `target_before`,
  `target_after`, `match`).
- System collections are skipped. Collections that exist only on the target
  are left alone.
- If a URI has no database path, set `SOURCE_DB_NAME` / `TARGET_DB_NAME`
  (or `DB_NAME` as a fallback for both).

```bash
# In your own terminal, after exporting the two URLs in that shell only:
python3 scripts/migrate_mongo.py            # dry-run, counts only
python3 scripts/migrate_mongo.py --apply    # writes; idempotent by _id
```

### Option C — Emergent cannot expose the production URI

Ask Emergent support for a `mongodump` of the production database for
`mnq-scalp-stack`, or for the production `MONGO_URL` so you can run Option
A or B yourself. Do not rely on the preview database.

### After the copy

Compare counts collection by collection. If anything is written to Emergent
between the export and the final cut-over, re-run the script with `--apply`
(upserts are idempotent) or re-dump only the changed collections.

Collections expected on production include: `users`, `user_sessions`,
`login_attempts`, `subscribers`, `payment_transactions`, `signals`,
`signal_events`, `trades`, `operator_orders`, `ati_commands`, `alerts`,
`watchlist`, `checklist`, `backtests`, `settings`, `proof_shots`,
`pnl_journal`, `copilot_sessions`, `copilot_messages`, `analytics_visits`,
`affiliate_clicks`, `presence`, `welcome_sequence`, `system_logs`, plus
`alert_deliveries` and `alert_delivery_claims` from PRs #17/#18. The script
copies every non-system collection it finds, including ones added later.
Indexes are recreated on backend startup.

---

## 4. Hosting the FastAPI backend

### Render (primary, repo already has `render.yaml`)

`render.yaml` defines a Python web service, root dir `backend`, one Uvicorn
worker, health check `GET /api/`, and **`autoDeploy: false`**. Leave
auto-deploy off until the cut-over is verified.

Why a paid always-on plan, not the free tier or serverless: the process
runs a 60s signal-engine loop, a resolver loop, a recap loop, and a
WebSocket fan-out. Engine state is in memory, so run **exactly one
instance and one worker**. The free plan sleeps and would stop those loops.

**Cost:** check current pricing on Render's site before you add a card.
The blueprint's `starter` plan has historically been around $7/month for a
small always-on instance; confirm the live price.

Steps:

1. Sign in at [render.com](https://render.com) with GitHub and grant access
   to `Mnqscalpstacks.-Dashboard-emergent`.
2. New → Blueprint → this repo, branch `main` (after this PR is merged, or
   from this branch if you want a staging service first).
3. Fill every `sync: false` variable in the Render dashboard yourself.
   Names must match §5. `DB_NAME` must equal the restored database name.
4. Manual deploy. Watch logs for a clean startup and no Mongo timeout.
5. Optional but recommended: custom domain `api.mnqscalpstacks.com` so
   auth cookies stay on the same site as `mnqscalpstacks.com`.

### Railway (alternative)

The repo also has `backend/Dockerfile`. On Railway, set the root directory
to `backend`, one replica, no sleep, and the same env var names. Start
command is the same Uvicorn line as in `render.yaml` (Railway will set
`PORT`).

**Cost:** check current pricing on Railway's site. A small always-on
container has historically been in a similar monthly range to Render
Starter; confirm before you add a card.

Fly.io is a third option (`fly launch` in `backend/`, one machine,
`min_machines_running = 1`, auto-stop off) if you prefer it later.

---

## 5. Environment variable names only

Never commit or paste values. Client-side variables may only hold public
URLs, never secrets.

### New backend host (Render / Railway)

Required:

| Name | Purpose |
|---|---|
| `MONGO_URL` | Atlas connection string |
| `DB_NAME` | Must match the restored database (the code default `test_database` is wrong for production) |
| `JWT_SECRET` | Signs access/refresh tokens. Reuse the Emergent value to keep existing sessions, or rotate (everyone signs in again) |
| `CORS_ORIGINS` | Comma list of exact frontend origins: `https://mnqscalpstacks.com,https://www.mnqscalpstacks.com,https://mnqscalpstacks-dashboard-emergent.vercel.app` |

Recommended / already used in production:

| Name | Purpose |
|---|---|
| `CORS_ORIGIN_REGEX` | Optional regex for Vercel preview URLs |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | Owner account seeded on startup |
| `ADMIN_EMAILS` | Comma list promoted to admin |
| `RETOOL_API_KEY` | `X-API-Key` for mutating endpoints. If unset, treat writes as a security review item |
| `SIGNAL_WEBHOOK_SECRET` | Secret the backend expects on `/api/signals/tradingview` (and the legacy path). This is what the Vercel receiver sends as `EMERGENT_WEBHOOK_SECRET` today |
| `DISCORD_WEBHOOK_URL` | Practice-alert delivery (PR #17). You set this; never log or return the URL |
| `DISCORD_INVITE_FREE` / `DISCORD_INVITE_PRO` / `DISCORD_INVITE_ELITE` | Tier invite links after checkout |
| `ALPHA_VANTAGE_KEY` | Stock quotes (defaults to `demo`) |
| `STRIPE_API_KEY` | Checkout sessions |
| `STRIPE_LIVE_SECRET_KEY` / `STRIPE_LIVE_WEBHOOK_SECRET` | Payment-link webhook |
| `COPILOT_ENABLED` | Default off unless `true` |
| `OPENAI_API_KEY` | Copilot via the local shim (replaces `EMERGENT_LLM_KEY`) |
| `XAI_API_KEY` | Grok provider for copilot |
| `EMERGENT_LLM_KEY` | Legacy fallback only; an Emergent key will not work as OpenAI. Prefer `OPENAI_API_KEY` and drop this |
| `AFFILIATE_URL_NINJATRADER` / `AFFILIATE_URL_TRADINGVIEW` / `AFFILIATE_URL_GPAY` / `AFFILIATE_URL_DISCORD` | Optional; safe defaults exist |
| `TV_DATA_MODE` | `delayed` (default) or `realtime` — this is a **label**, not a live broker feed |

Alert engine (PRs #17 / #18). Leave the approval flags unset until you
approve the pending Strategy A/B parameters. Only the exact value `true`
turns those confirmation alerts on (`1` / `yes` do not count).

| Name | Purpose |
|---|---|
| `STRATEGY_A_PARAMETERS_APPROVED` | Leave unset |
| `STRATEGY_B_PARAMETERS_APPROVED` | Leave unset |
| `ALERT_DEDUP_WINDOW_SECONDS` | Optional; has a default |
| `ALERT_DISCORD_RETRIES` | Optional; has a default |
| `ALERT_DISCORD_BACKOFF_BASE_SECONDS` | Optional; has a default |

Temporal stays off:

| Name | Purpose |
|---|---|
| `TEMPORAL_ENABLED` | Leave unset or `false` |
| `TEMPORAL_TASK_QUEUE` / `TEMPORAL_ADDRESS` / `TEMPORAL_NAMESPACE` / `TEMPORAL_API_KEY` / `TEMPORAL_TLS` / `TEMPORAL_TLS_CERT_PATH` / `TEMPORAL_TLS_KEY_PATH` | Only if Temporal is later approved |

`PORT` is set by the host. `PYTHON_VERSION` is set in `render.yaml`.

### Vercel (frontend + receiver)

| Name | Where | Purpose |
|---|---|---|
| `REACT_APP_BACKEND_URL` | Build-time, public | New backend origin, no trailing slash. Example later: `https://api.mnqscalpstacks.com` or the Render URL. Today it is `https://mnq-scalp-stack.emergent.host` |
| `REACT_APP_TV_SYMBOL` | Build-time, public | Optional chart symbol; has a default |
| `SIGNAL_WEBHOOK_SECRET` | Server-only, receiver | Secret TradingView sends to Vercel. You set and rotate this |
| `EMERGENT_WEBHOOK_SECRET` | Server-only, receiver | Secret the **backend** expects. The name is historical; after the move it is the new host's `SIGNAL_WEBHOOK_SECRET` |
| `UPSTREAM_WEBHOOK_URL` | Server-only, receiver, **new in this PR** | Optional. When unset, the receiver keeps forwarding to `https://mnq-scalp-stack.emergent.host/api/signals/tradingview`. When you are ready, set it to `https://<new-host>/api/signals/tradingview` |

`GET /api/signals/tradingview` reports `secret_configured`,
`upstream_configured`, and `upstream_url_overridden` as booleans only. It
never returns a URL or a secret.

### Josue's local NinjaTrader bridge only (not the host)

`SCALP_BACKEND_URL`, `SCALP_API_KEY`, `NT_INCOMING` — update the backend
URL on your PC after cut-over.

---

## 6. Pointing the frontend and the Vercel receiver at the new host

Do this only after the new backend is up and the read-only checks in §7
pass. TradingView itself stays on Emergent until §8.

1. **Frontend.** In the Vercel project, set Production (and Preview if you
   want) `REACT_APP_BACKEND_URL` to the new backend origin, no trailing
   slash. Redeploy. CRA bakes this in at build time, so a redeploy is
   required.
2. **Receiver upstream URL.** Before this PR, that URL was hardcoded to
   Emergent, so a code change was required to leave Emergent. This PR
   reads server-only `UPSTREAM_WEBHOOK_URL` and keeps the Emergent URL as
   the default, so nothing changes until you set the variable. After the
   new backend is serving `/api/signals/tradingview` and
   `EMERGENT_WEBHOOK_SECRET` matches that host's `SIGNAL_WEBHOOK_SECRET`,
   set `UPSTREAM_WEBHOOK_URL` to `https://<new-host>/api/signals/tradingview`
   (Production). You do not need another code change.
3. **Stripe, Retool, and the NinjaTrader bridge** also need their
   base URLs updated when you cut over. Stripe webhook signing secrets
   change if you create a new endpoint; update
   `STRIPE_LIVE_WEBHOOK_SECRET` yourself.

`www.mnqscalpstacks.com` has had a broken TLS certificate. Fix or drop
`www` as a separate task; do not block the backend move on it.

---

## 7. Read-only verification checks

Run these before switching the frontend, and again after. Do not POST
signals that create cards, and do not use the unauthenticated legacy
`/api/webhook/tradingview` path.

On the **new backend**, while Emergent is still the public frontend:

- `GET /api/` returns `{"message": "Trading Command Center API"}`.
- `/api/docs` loads.
- An OPTIONS preflight from `Origin: https://mnqscalpstacks.com` echoes
  that origin in `Access-Control-Allow-Origin`.
- `/api/admin/overview` returns 401 or 403 without a login (not 200 with
  subscriber or revenue data).
- The legacy webhook path rejects unauthorized requests **before** any
  write (confirm in code first, then one unauthorized POST is enough).
- WebSocket `wss://<new-host>/api/ws/mnq` receives MNQ snapshots. The tape
  is delayed Yahoo data, not a live broker feed.
- Sign in with the admin email/password against a preview frontend pointed
  at the new URL. Journal, signals, and user counts match the copy.
- After a couple of minutes, logs show the engine loop and no duplicate
  Discord posts.

On **Vercel**, after you set `UPSTREAM_WEBHOOK_URL` (and not before you
mean to leave Emergent):

- `GET https://mnqscalpstacks.com/api/signals/tradingview` returns 200
  JSON with `receiver: "vercel"`, `secret_configured: true`,
  `upstream_configured: true`, `upstream_url_overridden: true`.
- No CORS error on sign-in from `mnqscalpstacks.com`.

Compare public (or admin-authenticated) signal stats and a sample of
`_id`s against the pre-copy counts. They must match.

---

## 8. Switching TradingView last — only after the 4-point check

TradingView stays aimed at Emergent until **all four** are true on the
path you are about to use (Vercel receiver → new backend → same Atlas DB
the dashboard reads):

1. **JSON responses** from the Vercel receiver (already true today).
2. **A server-only secret** — `SIGNAL_WEBHOOK_SECRET` is set on Vercel
   and is not in client code or `REACT_APP_` variables (the slot is
   already there; you confirm it).
3. **Signals land in the same database the dashboard reads** — after
   `UPSTREAM_WEBHOOK_URL` points at the new host, and that host uses the
   Atlas `MONGO_URL` / `DB_NAME` the dashboard is reading.
4. **Honest labels** — no misleading LIVE badge on delayed, paper, or
   test cards.

Until 3 and 4 pass, do not change the TradingView alert URL.

When they pass and you approve it, point TradingView at
`https://mnqscalpstacks.com/api/signals/tradingview` (or the Vercel
deployment URL), not at Emergent and not at the unauthenticated legacy
path. Then run one PAPER end-to-end test, and only with a separate
explicit approval.

Never POST `CLOSE`: it expires every active card.

---

## 9. Rollback — keep Emergent running until verified

Leave the Emergent deployment up until the new host has been stable
(plan for 24–48 hours, longer if needed).

To roll back:

1. Set Vercel `REACT_APP_BACKEND_URL` back to
   `https://mnq-scalp-stack.emergent.host` and redeploy.
2. Remove `UPSTREAM_WEBHOOK_URL` (or leave it unset) so the receiver
   default is Emergent again. Confirm
   `upstream_url_overridden: false` on the health GET.
3. Point Stripe, Retool, and the NinjaTrader bridge back at Emergent.
4. If TradingView was switched, point it back at the Emergent URL you
   were using.

Do not cancel Emergent, rotate every secret, or delete the Emergent
Mongo until you have confirmed the new host and a rollback is no longer
needed. If you later decommission Emergent, rotate secrets that lived
there (`JWT_SECRET`, Stripe, Discord, Retool, webhook secrets).

---

## 10. Founder-only steps (checklist)

- [ ] Decide a move date. Until then, stay on Emergent.
- [ ] Atlas: M0 cluster, database user, network access. Connection string
      stays in your password manager.
- [ ] Private copy of current Emergent env values (names in §5) and the
      production `DB_NAME`.
- [ ] Production export or copy (Option A, B, or C). Preview DB is not
      production.
- [ ] Dry-run `scripts/migrate_mongo.py`, then `--apply`, on your machine.
      Counts match.
- [ ] Create the Render (or Railway) service. Check current pricing first.
      Leave `autoDeploy` off.
- [ ] Enter env vars on the new host yourself. Leave Temporal and Strategy
      A/B approval flags off.
- [ ] Optional: `api.mnqscalpstacks.com`.
- [ ] Read-only checks on the new backend (§7) while the public site still
      uses Emergent.
- [ ] Set Vercel `REACT_APP_BACKEND_URL` and redeploy.
- [ ] Set Vercel `UPSTREAM_WEBHOOK_URL` only when the new backend is the
      intended upstream. Set `EMERGENT_WEBHOOK_SECRET` to the new host's
      `SIGNAL_WEBHOOK_SECRET`.
- [ ] Repeat §7 against the production frontend.
- [ ] 4-point check. Only then approve a TradingView URL change and one
      PAPER test.
- [ ] Keep Emergent running until verified. Only you cancel it later.

---

## Related docs

`docs/MIGRATION.md` is the earlier PR #7 plan. Prefer this document: it
includes the Vercel receiver, the copy script, post-#17/#18 env vars, and
the 4-point TradingView gate. Do not follow §7 of the older doc as
written (it pointed TradingView straight at the new backend).
