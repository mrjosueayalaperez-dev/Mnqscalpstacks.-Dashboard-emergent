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

## Configured
- Discord Webhook: LIVE
- Stripe: test key
- OpenAI: via Emergent LLM key

## Backlog
- P1: Refactor App.js (1500+ lines) and server.py (2000+ lines) into modular files
- P2: Live Broker API connection (replace simulator)
- P2: Functional Google Pay via Stripe Payment Element
