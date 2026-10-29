# MNQ Scalp Stacks — Free Hosting Runbook

> **Superseded for the backend move:** see [docs/MIGRATION.md](docs/MIGRATION.md) (Render Starter, not free — the free tier sleeps and stops the signal engine loops).

**Goal:** the full app (React frontend + FastAPI backend + MongoDB) running free,
on **mnqscalpstacks.com**, working like it did on Emergent.

**Free stack:** Vercel (frontend) + Render (backend) + MongoDB Atlas M0 (database) = $0.

> One honest note: Render's free tier sleeps after 15 minutes with no visitors —
> the first visit after a nap takes ~30–60 seconds to wake up. After that it's normal speed.

---

## Step 1 — Database (MongoDB Atlas) — Josue

1. Go to https://cloud.mongodb.com and create a free account.
2. Create a cluster: choose **M0 Free** tier, any nearby region.
3. Create a database user (username + password — save them).
4. Network Access → **Allow access from anywhere** (`0.0.0.0/0`).
   (Render's servers don't have fixed addresses, so this is required on the free tier.)
5. Connect → **Drivers** → Python → copy the connection string.
   It looks like: `mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/`
6. Send the connection string to Zelator (it goes straight into Render's env vars, never into the code).

## Step 2 — Backend (Render) — Zelator + Josue

1. Commit `deploy/render.yaml` to the repo root and push.
2. Go to https://render.com, sign up (GitHub login is easiest).
3. **New → Blueprint** → connect the `Mnqscalpstacks.-Dashboard-emergent` repo.
4. Render reads `render.yaml` and creates the web service.
5. In the service's **Environment** tab, fill in:
   - `MONGO_URL` → the Atlas connection string from Step 1
   - `DISCORD_WEBHOOK_URL` → your Discord webhook (same one Emergent used)
6. Deploy. When it's live, copy the service URL, e.g. `https://mnq-scalp-stacks-backend.onrender.com`
7. Sanity check: open `https://<your-service>.onrender.com/docs` — you should see the API docs.

## Step 3 — Frontend (Vercel) — Zelator + Josue

1. Go to https://vercel.com, sign up (GitHub login is easiest).
2. **Add New → Project** → import the `Mnqscalpstacks.-Dashboard-emergent` repo.
3. Set **Root Directory** to `frontend`.
4. Framework preset: Create React App. Build command and output are auto-detected.
5. Add environment variable: `REACT_APP_BACKEND_URL` = the Render URL from Step 2
   (e.g. `https://mnq-scalp-stacks-backend.onrender.com` — no trailing slash).
6. Deploy. You get a `*.vercel.app` URL — the app should load and talk to the backend.

## Step 4 — Custom domain (name.com → Vercel) — Josue

1. In Vercel: project **Settings → Domains** → add `mnqscalpstacks.com`
   (add `www.mnqscalpstacks.com` too — Vercel redirects it).
2. Vercel shows you the DNS records to add (an `A` record and/or `CNAME`).
3. In name.com: **My Domains → mnqscalpstacks.com → DNS Records** → add exactly what Vercel shows.
4. Wait a few minutes → Vercel provisions HTTPS automatically. Done.

Optional: point `api.mnqscalpstacks.com` at Render (Render dashboard → Custom Domain →
add the CNAME in name.com), then update `REACT_APP_BACKEND_URL` and redeploy the frontend.

## Step 5 — Verify everything

- [ ] `https://mnqscalpstacks.com` loads the dashboard
- [ ] Charts/data load (backend reachable — check `/docs` on Render)
- [ ] Journal entries save and persist (MongoDB connected)
- [ ] A test signal fires the Discord webhook
- [ ] Phone + desktop layouts look right

## If something breaks

- Backend won't start → check Render **Logs** tab; 9 times out of 10 it's a missing env var.
- Frontend shows but no data → `REACT_APP_BACKEND_URL` is wrong or the backend is asleep (wait 60s, refresh).
- Database errors → check the Atlas connection string and the `0.0.0.0/0` network rule.
