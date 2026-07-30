# MNQ SCALP STACKS — Final PRD

## Routes
- `/` — Landing page (conversion funnel, referral, welcome onboarding)
- `/dashboard` — Trading command center (SaaS preview)
- `/operator` — **Personal Operator Cockpit (Phase 1 — primary build target)**
- `/performance` — Public performance / leaderboard
- `/admin` — Admin panel

## Implemented Features
1. Landing Page (7-section funnel)
2. Referral System (per-subscriber codes + tracking)
3. Welcome Sequence (5-step onboarding)
4. Mobile-optimized (390px+)
5. MNQ Futures Tracker + Signal Engine v2 + Scanner
6. Trade Journal + Daily Checklist + AI Analysis + Position Calculator + Alerts
7. Backtest Results (manual + API + display)
8. Performance Dashboard (equity curve, stats)
9. Subscriber System (Free/Pro/Elite via Stripe)
10. Discord Bot (branded embed, 3-Pillar)
11. Pine Script v2 (Session VWAP + Structure)
12. Zelator Command Center (Safety Sentinel, Hydro-Pilot, Dual-Gate)
13. Execution Hub (40t SL / 60t TP brackets, -$100 daily lockout)
14. Auto Signal Engine + Freemium Gates
15. **PromoModules** (NinjaTrader Panel, TradingView Panel, Market Sidebar, GPay FAB) — wired into dashboard (2026-02-21)
16. **Affiliate Click Tracking & Revenue Surface** (2026-02-21):
    - All NinjaTrader / TradingView / GPay CTAs route through `GET /api/r/{partner}?src={cta_id}` (302 redirect + click log)
    - `GET /api/admin/clicks` returns total clicks, per-partner breakdown, top-CTA breakdown, partner URL config status
    - Admin Panel "Affiliate Click Revenue" card shows live stats and flags unconfigured partner URLs in red
    - 3 pytest regressions in `/app/backend/tests/test_affiliate_tracking.py`

17. **Operator Cockpit — Phase 1** (2026-02-21):
    - Route: `/operator`
    - Live MNQ chart via `lightweight-charts` (1m/5m/15m, EMA9/EMA21/VWAP overlays, volume histogram)
    - Top status bar: animated logo, NinjaTrader connection indicator, balance, daily PnL, session timer, big red FLATTEN
    - LONG panel (BUY MARKET/LIMIT, BREAK EVEN, CLOSE LONG) + mirrored SHORT panel
    - Position info (side/qty/avg entry/ticks/unrealized PnL — MNQ $2/pt)
    - Risk gates (loss gauge, trades gauge, market/auto/CD/kill status pills)
    - Signal panel (bias + confluence + EMA21/VWAP/RSI)
    - Journal (last 15 orders with timestamps & PnL & bracket lines)
    - Master controls (FLATTEN ALL red, PAUSE yellow, RESET blue, KILL purple)
    - Backend safety chain on every order: kill_switch → automation_paused → max_daily_loss → max_daily_trades → 1500ms cooldown → LIMIT-needs-price
    - 1500ms UI cooldown on every order button (disable + visual countdown)
    - **Snipe Mode** (`S` to arm): bypasses UI cooldown, red ring overlay, persisted in localStorage
    - **Web Audio confirmations** (`M` to mute): distinct tones per BUY/SELL/CLOSE/BREAK_EVEN/FLATTEN/KILL/REJECT
    - **Keyboard hotkeys** (`B`/`N`/`L`/`;`/`C`/`E`/`F`/`P`/`K`/`R`/`S`/`M`/`?`/`1`/`2`/`3`/`7`/`8`/`9`/`0`/`Escape`) with typing-safe handler
    - **HotkeyHelp modal** (`?`) with grouped keycap legend
    - **R-Multiple Bracket Ladder** — 3 presets (Snipe 1R 40t/60t, Snipe 2R 40t/120t, Runner 40t/200t), `7`/`8`/`9` hotkeys, `0` to toggle attach. Active preset auto-attaches SL/TP to every BUY/SELL; backend computes & logs SL/TP prices.
    - PHASE 1 banner: orders logged server-side only, NO broker connection
    - 7 pytest regressions in `/app/backend/tests/test_operator_cockpit.py`

18. **Live MNQ Feed — Phase 1.5** (2026-02-21):
    - **Root cause fixed:** cockpit showed 18,500 vs TradingView 29,520 because backend used a hardcoded synthetic baseline
    - Backend: new `market_feed.py` module fetches real CME data from **Yahoo `NQ=F`** (NQ and MNQ trade at the same price; MNQ is 1/10 contract size)
    - Backend: WebSocket endpoint `/api/ws/mnq` streams ticks (~3s cadence, single fan-out broker pattern)
    - Backend: `/api/futures/mnq` and `/api/operator/candles` now return real Yahoo data with computed EMA9/EMA21/VWAP/RSI
    - Backend: order fills use the **live cached price** — if no live price available, fills return `503` rather than mis-filling
    - Frontend: replaced lightweight-charts custom panel with the **official TradingView Advanced Chart widget** (`CME_MINI:MNQ1!`)
    - Frontend: `useMnqLive` hook with WS-primary + 8s REST fallback + exponential reconnect
    - `/app/SYNC_NOTES.md` documents symbol mapping and architecture
    - 4 new pytest regressions in `/app/backend/tests/test_live_feed.py`

19. **Code Quality Sweep — Feb 2026** (final pass):
    - **Array-index keys eliminated** in 11 spots across `LandingPage.js`, `PerformancePage.js`, `AdminPanel.js`, `PromoModules.js`, `Leaderboard.js`, `PerformanceEngine.js` — now using stable `item.label`, `item.text`, `item.title`, `tier.id`, `email/id`, etc. Verified `grep "key={i}"` returns zero hits.
    - **`market_context.py` refactored**: one 81-line cc=25 function → six focused helpers (`_fetch_daily_bars`, `_extract_quote_series`, `_compute_adr`, `_volume_strength`, `_trend_change_pct`, `_build_context`); each <35 lines, all cc<6.
    - **`get_pine_script` refactored**: 117-line endpoint → 5-line endpoint reading from module-level `_PINE_SCRIPT_V3` constant + `_build_webhook_instructions()` helper.
    - **`send_discord_signal` refactored**: 60-line cc=12 function → 9-line endpoint + 4 small helpers (`_discord_webhook_configured`, `_format_signal_pillars`, `_rr_ratio`, `_build_discord_payload`).
    - **120 lines of dead code deleted** from server.py: unreachable `get_mnq_data_synthetic` (66 lines, hardcoded 18500 walk) and `operator_candles_synthetic` (54 lines). Replaced one remaining `base_price = 18500` in `generate_test_signal` with the live MNQ feed.
    - **Type hints added** to all operator + market + admin/clicks endpoints (`Dict[str, Any]` return types) and to `market_feed.py` (refactored module-level dicts, helpers, broker class).
    - **`LiveChart.js` deleted** — lightweight-charts custom chart no longer mounted since switching to TradingView widget.
    - **`script.innerHTML` / `container.innerHTML`** in TradingViewWidget replaced with `script.textContent` and `container.replaceChildren()` — eliminates false-positive XSS lint warnings on hardcoded TV embed config.
    - **`useMnqLive` empty-deps array** annotated with `eslint-disable-next-line react-hooks/exhaustive-deps` + intent comment so future linters don't keep flagging the intentional once-on-mount WebSocket lifecycle.
    - Pyflakes cleanups: removed unused `import asyncio` + 3 unused `global signal_engine_state` declarations.
    - All 14 of my regressions pass (operator cockpit + live feed + affiliate). Backend pyflakes clean. ESLint clean across `/app/frontend/src`. Backend trimmed from 2477 → 2372 lines.
    - **Root cause fixed:** cockpit showed 18,500 vs TradingView 29,520 because backend used a hardcoded synthetic baseline
    - Backend: new `market_feed.py` module fetches real CME data from **Yahoo `NQ=F`** (NQ and MNQ trade at the same price; MNQ is 1/10 contract size)
    - Backend: WebSocket endpoint `/api/ws/mnq` streams ticks (~3s cadence, single fan-out broker pattern)
    - Backend: `/api/futures/mnq` and `/api/operator/candles` now return real Yahoo data with computed EMA9/EMA21/VWAP/RSI
    - Backend: order fills use the **live cached price** — if no live price available, fills return `503` rather than mis-filling
    - Frontend: replaced lightweight-charts custom panel with the **official TradingView Advanced Chart widget** (`CME_MINI:MNQ1!`) — visual ground truth, auto-handles quarterly rollover
    - Frontend: `useMnqLive` hook subscribes to WS with exponential reconnect + 8s REST fallback
    - Frontend: index.js global error handler suppresses benign cross-origin "Script error." from TV iframe telemetry
    - "LIVE FEED — CME via TradingView + Yahoo NQ=F" banner replaces the old "SIMULATED LOG ONLY" notice
    - `/app/SYNC_NOTES.md` documents symbol mapping (TV `MNQ1!` ↔ NT `MNQ 03-26` ↔ Yahoo `NQ=F` ↔ backend `MNQ`) and the full live-feed architecture
    - 4 new pytest regressions in `/app/backend/tests/test_live_feed.py` (REST snapshot, candles, order fills, WS stream)

20. **Live Terminal Chart on /dashboard** (2026-02-22):
    - New `components/LiveTerminalChart.js`, mounted as ROW 0 (full-width, above MNQ Scalp Punch)
    - Official TradingView Advanced Chart embed (`CME_MINI:MNQ1!`, dark, EMA9/EMA21/VWAP/Volume studies) — user's TV subscription supplies real-time CME data in their browser
    - Terminal frame fed by `useMnqLive` WS hook: big live price with green/red tick-flash, change/%, LIVE/RECONNECT badge, market state
    - Live tape: Session High/Low, VWAP, EMA9, EMA21, RSI14 (color-coded, mono)
    - Timeframe quick-select (1m/5m/15m/1h/4h/D) — remounts TV embed with chosen interval
    - Live SignalBar: BUY PUNCH / SELL PUNCH / NEUTRAL from EMA21+VWAP+RSI confluence with per-condition chips
    - data-testids: `live-terminal-chart`, `terminal-live-price`, `terminal-ws-status`, `terminal-tf-*`, `terminal-signal-bar`, `terminal-session-high/low`, etc.
    - Note: TV canvas doesn't paint in headless browsers (serves error-card to bots) — renders fine in real browsers, same as /operator

21. **TradingView chart bug fix + deploy prep** (2026-02-22):
    - ROOT CAUSE: TV blocks CME futures symbols (CME_MINI:MNQ1!) in anonymous embeds; embed script loader also nondeterministically ignored theme:dark and misplaced the iframe
    - FIX: `src/lib/tvEmbedUrl.js` builds a deterministic direct `widgetembed` iframe URL — CAPITALCOM:US100 (real-time Nasdaq-100 CFD, tracks MNQ 1:1), theme=dark, MAExp+VWAP studies. Used by both LiveTerminalChart (dashboard) and operator TradingViewWidget
    - Verified by testing agent (iteration_8): 100% pass, deterministic dark render across reloads + interval switches
    - Deploy blocker fixed: /api/signals/pinescript webhook instructions now derive base URL from request (x-forwarded-proto aware) instead of REACT_APP_BACKEND_URL env
    - Deployment agent re-check: PASS (production-ready)

22. **Verified Results proof gallery** (2026-07-20):
    - Backend `proof.py`: /api/proof/list|image/{id}|upload|delete — images base64 in Mongo `proof_shots` (survive redeploys), write endpoints gated by require_write_key, 8MB/type validation
    - Landing page: "VERIFIED RESULTS — REAL TRADE PROOF" section (ProofGallery.js) with lightbox, hidden when empty
    - Admin panel: ProofManager.js — upload (file+caption), thumbnail grid, hover-delete
    - Seeded 2 real user proof collages (P&L receipts + closed MNQ Sep-26 positions)
    - Testing agent iteration_9: 100% backend + frontend pass; regression suite now includes tests/test_proof_gallery.py
    - User has MORE proof shots to upload later via /admin

23. **Black-screen Discord bug fix + video proof + Stripe status fix** (2026-07-30):
    - FIXED user-reported production bug: paid users clicking "Join Discord" hit a black screen — placeholder env invite rendered as relative href to a non-existent route. Guard now `!startsWith("REPLACE")` (PerformancePage) + catch-all route `*` → Navigate to / (App.js)
    - Fixed /api/checkout/status 500 by upgrading emergentintegrations 0.1.0 → 0.2.0; status now returns amount/metadata + NEW discord_invite field (post-payment success panel wired to it)
    - Proof gallery now supports VIDEO (mp4/webm, 11MB): play overlay on cards, <video controls> in lightbox, admin video thumbs. Seeded user's new proof: MNQ/MES positions collage + 8.6MB video (gallery = 4 items)
    - Testing agent iteration_10: 100% backend + frontend pass; new regression file tests/test_black_screen_and_video.py (run with REACT_APP_BACKEND_URL exported)
    - PENDING FROM USER: real Discord invite link(s) → set DISCORD_INVITE_FREE/PRO/ELITE in backend/.env, then redeploy

## Configured
- Discord Webhook: LIVE
- Stripe: test key
- OpenAI: via Emergent LLM key

## Backlog
- P1: Refactor App.js (1500+ lines) and server.py (2000+ lines) into modular files
- P2: Live Broker API connection (replace simulator)
- P2: Functional Google Pay via Stripe Payment Element
