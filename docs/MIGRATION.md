# Backend migration: Emergent.host → Render + MongoDB Atlas

Status: **prepared, not executed.** Nothing in this branch touches production or deploys anything.
Frontend is already on Vercel; only the backend + database move.

| | Today (Emergent) | Target |
|---|---|---|
| Backend | `https://mnq-scalp-stack.emergent.host` (FastAPI pod) | Render web service, **Starter plan ($7/mo, always-on)** |
| Database | Emergent-managed MongoDB (per-environment; preview ≠ production) | MongoDB Atlas **M0 free** |
| Frontend | Vercel, `REACT_APP_BACKEND_URL=https://mnq-scalp-stack.emergent.host` | Vercel, `REACT_APP_BACKEND_URL=<new backend URL>` |

---

## 1. What the backend is

- **Framework:** FastAPI 0.110 on Uvicorn, Motor (async MongoDB). Entrypoint `backend/server.py` → `app`.
- **Start:** `uvicorn server:app --host 0.0.0.0 --port $PORT --workers 1` (run from `backend/`).
- **Python:** 3.12 (pandas 3 / numpy 2.4 need ≥ 3.11). Dependencies: `backend/requirements.txt` (installs cleanly outside Emergent; `import server` ≈ 210 MB RSS → fits 512 MB).
- **Health check:** `GET /api/` → `{"message": "Trading Command Center API"}`. API docs at `/api/docs`.
- **Always-on requirements (why not serverless / not Render free):**
  - `@app.on_event("startup")` launches `live_signal_engine_loop` (every 60 s), `signal_resolver_loop`, `daily_recap_loop` (30 s tick).
  - WebSocket `GET /api/ws/mnq` with a 3 s fan-out tick broker (`market_feed.TickBroker`).
  - Engine state (`signal_engine_state`, operator state) is **in-memory** → run **1 instance, 1 worker**. More workers/instances = duplicate signals + Discord posts.

## 2. Environment variables (names only — never commit values)

| Name | Required | Purpose |
|---|---|---|
| `MONGO_URL` | **yes** | Mongo connection string (defaults to localhost → app fails without it) |
| `DB_NAME` | **yes** | Database name (default `test_database`!). Must match the restored DB name |
| `JWT_SECRET` | **yes** | Signs access/refresh JWTs (`auth.py` → `os.environ["JWT_SECRET"]`, KeyError on login if missing). Reuse old value to keep sessions, or rotate (everyone re-logs in) |
| `CORS_ORIGINS` | **yes (prod)** | Comma list of exact frontend origins (Vercel prod + custom domain). Default `*` |
| `CORS_ORIGIN_REGEX` | optional | Regex for Vercel preview URLs (new in this branch) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | recommended | Idempotent owner account seeded on startup |
| `ADMIN_EMAILS` | optional | Comma list promoted to admin role |
| `RETOOL_API_KEY` | recommended | `X-API-Key` for mutating endpoints. **On main, unset = writes are OPEN.** (PR #6 makes it fail-closed) |
| `SIGNAL_WEBHOOK_SECRET` | recommended | TradingView webhook secret (`/api/webhook/tradingview`, `/api/signals/tradingview`) |
| `DISCORD_WEBHOOK_URL` | optional | Signal/owner alerts to Discord |
| `DISCORD_INVITE_FREE` / `_PRO` / `_ELITE` | optional | Tier invite links returned after checkout |
| `ALPHA_VANTAGE_KEY` | optional | Stock quotes (defaults to `demo`) |
| `STRIPE_API_KEY` | optional | Checkout sessions (`/api/checkout/*`, webhook `/api/webhook/stripe`) |
| `STRIPE_LIVE_SECRET_KEY` / `STRIPE_LIVE_WEBHOOK_SECRET` | optional | Payment-link verification webhook `/api/webhook/stripe-live` |
| `COPILOT_ENABLED` | optional | `true` enables the copilot router (default false) |
| `OPENAI_API_KEY` | optional | GPT copilot via litellm shim — **replacement for `EMERGENT_LLM_KEY`** |
| `XAI_API_KEY` | optional | Grok provider for copilot / chat stream |
| `EMERGENT_LLM_KEY` | legacy | Only a fallback in the shim. An Emergent universal key will not work with OpenAI directly — drop it |
| `AFFILIATE_URL_NINJATRADER` / `_TRADINGVIEW` / `_GPAY` / `_DISCORD` | optional | Outbound affiliate links (safe defaults) |
| `TV_DATA_MODE` | optional, **PR #6 only** | `delayed` (default) / `realtime` price label |
| `SCALP_BACKEND_URL` / `SCALP_API_KEY` | n/a for server | Read by the local NinjaTrader bridge script (`bridge_template.py`) on Josue's PC — update its backend URL after cut-over |

## 3. Emergent-specific dependencies

| Dependency | Status off Emergent | Action |
|---|---|---|
| `emergentintegrations` package (LLM chat, Stripe checkout) | **Already replaced** by local shim `backend/emergentintegrations/` (litellm + official `stripe` SDK). Not in requirements. | Set `OPENAI_API_KEY` instead of `EMERGENT_LLM_KEY`. |
| Emergent Google login: frontend `AuthPage.js` → `https://auth.emergentagent.com/?redirect=…`; backend `POST /api/auth/session` → `https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data` | **BREAKS / at risk.** It is Emergent's hosted OAuth broker; expect it to stop when the Emergent account/app is cancelled. | Short term: hide the Google button; email/password JWT login already works. Replacement (follow-up PR): Google Identity Services in the frontend (`@react-oauth/google`) → new `POST /api/auth/google` verifying the ID token with `google-auth` (already in requirements) against `GOOGLE_CLIENT_ID`, matching users **by email** so existing Google users keep their account. Google-only users have no password; they need the new Google login or a password-set flow. |
| `.emergent/` (cron watcher, `emergent.yml` image) | Unused off Emergent; no `crons.yml` exists, all scheduling is in-process. | Ignore; delete after cut-over. |
| Frontend share card text `mnq-scalp-stack.emergent.host` (`frontend/src/lib/shareCard.js`) | Cosmetic | Change to `mnqscalpstacks.com` in a follow-up. |
| Stripe webhooks / TradingView alerts / Retool / NinjaTrader bridge pointed at `mnq-scalp-stack.emergent.host` | **Break at cut-over** | Re-point to the new backend URL (step 7). |

## 4. Database

Collections used: `users`, `user_sessions`, `login_attempts`, `subscribers`, `payment_transactions`, `signals`, `signal_events`, `trades`, `operator_orders`, `ati_commands`, `alerts`, `watchlist`, `checklist`, `backtests`, `settings`, `proof_shots` (proof images stored base64), `pnl_journal`, `copilot_sessions`, `copilot_messages`, `analytics_visits`, `affiliate_clicks`, `presence`, `welcome_sequence`, `system_logs`.
Indexes are recreated on startup (`users.email` unique, `analytics_visits` compound unique, `pnl_journal`, etc.).

**Production data lives in Emergent's managed Mongo for the deployed app** (separate from the preview pod's local Mongo). It must be exported with `mongodump` and restored to Atlas. Whether Emergent exposes the production connection string is the main blocker — see step 2.

---

## Cut-over checklist

### Step 0 — Prereqs (Josue)
- [ ] Decide order: merge PR #6 (P0 hardening) **before** cut-over if possible, so the new host starts fail-closed (writes/webhooks locked). Otherwise set `RETOOL_API_KEY` + `SIGNAL_WEBHOOK_SECRET` on day one.
- [ ] Copy the **names** in §2 and, privately, their current values from Emergent's deployment env panel into a password manager. Do not paste them into chat, issues, or git.

### Step 1 — MongoDB Atlas (Josue)
- [ ] https://cloud.mongodb.com → create project → **M0 Free** cluster, AWS `us-east-1` (matches Render Virginia).
- [ ] Database Access → user with `readWrite` on the target DB (strong generated password).
- [ ] Network Access → `0.0.0.0/0` (Render has no static egress IP on Starter). 
- [ ] Connect → Drivers → copy `mongodb+srv://…` string (this is `MONGO_URL`).

### Step 2 — Export data from Emergent (Josue, with Emergent)
- [ ] Get access to the **production** DB: Emergent deployment settings / support ("please give me a `mongodump` or the production `MONGO_URL` for app mnq-scalp-stack; I'm moving off the platform"). Note the production `DB_NAME`.
- [ ] If a connection string is provided, from any machine with MongoDB Database Tools:
  ```bash
  mongodump --uri "$EMERGENT_MONGO_URL" --db "$EMERGENT_DB_NAME" --gzip --archive=mnq-prod.archive.gz
  ```
- [ ] If Emergent only gives preview-pod access: the preview DB is **not** production (users, payments, proofs differ). Ask support for the prod dump; last resort is a one-off admin export endpoint deployed to Emergent (costs a redeploy) — don't rely on it.
- [ ] Record per-collection counts (`db.<coll>.countDocuments()`) for verification.

### Step 3 — Import into Atlas
- [ ] ```bash
  mongorestore --uri "$ATLAS_MONGO_URL" --gzip --archive=mnq-prod.archive.gz \
    --nsInclude "$EMERGENT_DB_NAME.*"   # keep the same DB name, or use --nsFrom/--nsTo to rename
  ```
- [ ] Compare counts with step 2. Delete the local archive afterwards (contains user emails + password hashes).

### Step 4 — Create the Render service (Josue + agent)
- [ ] https://render.com → sign in with GitHub → grant access to `Mnqscalpstacks.-Dashboard-emergent`.
- [ ] Add a payment card (Starter = $7/mo; free plan sleeps and kills the engine loops).
- [ ] New → **Blueprint** → select repo, branch `main` (after this PR merges) → Render reads `render.yaml`.
- [ ] Fill every `sync: false` variable from §2 in the dashboard (names exactly as listed). `DB_NAME` = restored DB name. `CORS_ORIGINS` = Vercel production URL(s) + `https://mnqscalpstacks.com,https://www.mnqscalpstacks.com` if used.
- [ ] Manual deploy. Watch logs for `Application startup complete` and no Mongo timeout.
- Alternative hosts: `backend/Dockerfile` works on Railway (root dir `backend`) or Fly.io (`fly launch` in `backend/`, 1 machine, `min_machines_running = 1`, `auto_stop_machines = "off"`).

### Step 5 — Optional custom API domain (recommended)
- [ ] Render → Settings → Custom Domain `api.mnqscalpstacks.com`; add the CNAME at name.com.
  Auth uses `SameSite=None; Secure` cookies; keeping API and site on the same registrable domain avoids third‑party‑cookie blocking (Safari/ITP).

### Step 6 — Smoke test the new backend (before switching the frontend)
- [ ] `curl -s https://<new-backend>/api/` → `{"message":"Trading Command Center API"}`
- [ ] `/api/docs` loads.
- [ ] `curl -s -i -X OPTIONS https://<new-backend>/api/ -H 'Origin: https://<vercel-domain>' -H 'Access-Control-Request-Method: GET'` → `access-control-allow-origin` echoes the Vercel origin.
- [ ] Websocket: `npx wscat -c wss://<new-backend>/api/ws/mnq` → MNQ snapshots every ~3 s.
- [ ] Log in with the admin account (email/password) via a Vercel **preview** deploy pointed at the new URL; open journal, signals, admin users list (counts match step 2).
- [ ] After ~2 min, logs show the live engine evaluating (60 s loop) and no duplicate Discord posts.

### Step 7 — Cut over
- [ ] Vercel → Project → Settings → Environment Variables → `REACT_APP_BACKEND_URL` = new backend URL (no trailing slash) for Production (and Preview) → **Redeploy** (CRA bakes it at build time).
- [ ] Stripe Dashboard → Developers → Webhooks: change `…/api/webhook/stripe` and `…/api/webhook/stripe-live` endpoints to the new host (new signing secret → update `STRIPE_LIVE_WEBHOOK_SECRET`).
- [ ] TradingView alerts: webhook URL → `https://<new-backend>/api/webhook/tradingview` (or `/api/signals/tradingview`).
- [ ] Retool resources base URL → new host. NinjaTrader bridge `SCALP_BACKEND_URL` → new host.
- [ ] Repeat Step 6 against production frontend.

### Step 8 — Decommission Emergent (only after 24–48 h stable)
- [ ] Final incremental check: any new users/payments written to Emergent between export and cut-over? If yes, re-dump those collections and `mongorestore` with `--nsInclude` for just those.
- [ ] Cancel Emergent subscription / delete deployment. Rotate any secret that lived on Emergent (`JWT_SECRET`, Stripe, Discord webhook, Retool key, webhook secret).
- [ ] Follow-up PR: remove `.emergent/`, replace Emergent Google auth, update share card text.

## Rollback
Set Vercel `REACT_APP_BACKEND_URL` back to `https://mnq-scalp-stack.emergent.host` and redeploy (only while Emergent is still running), and point Stripe/TradingView webhooks back.
