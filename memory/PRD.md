# MNQ SCALP STACKS — Final PRD

## Routes
- `/` — Landing page (conversion funnel, referral, welcome onboarding)
- `/dashboard` — Trading command center
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

## Configured
- Discord Webhook: LIVE
- Stripe: test key
- OpenAI: via Emergent LLM key

## Backlog
- P1: Refactor App.js (1500+ lines) and server.py (2000+ lines) into modular files
- P2: Live Broker API connection (replace simulator)
- P2: Functional Google Pay via Stripe Payment Element
