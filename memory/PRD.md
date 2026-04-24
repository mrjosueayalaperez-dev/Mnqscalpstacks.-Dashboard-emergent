# Trading Command Center - Final PRD

## System Overview
MNQ SCALP STACKS SaaS — Full trading signal platform with conversion funnel, signal engine, dashboard, and monetization.

## Routes
- `/` — Landing page (ad funnel conversion)
- `/dashboard` — Trading command center (all widgets)
- `/performance` — Public performance page (shareable, subscriber conversion)

## Tech Stack
- React 19, Tailwind CSS, Recharts, React Router, Sonner, Lucide
- FastAPI, MongoDB (Motor), httpx
- OpenAI GPT-4o (Emergent LLM Key), Alpha Vantage, Stripe, Discord

## All Features
1. Landing Page (hero, problem, solution, before/after, how it works, stats, pricing, CTA)
2. MNQ Futures Tracker (VWAP, EMA, RSI, setup signals)
3. Signal Engine v2 (Session VWAP + Structure, webhook, kill switch, Discord delivery)
4. Stock Watchlist + Scanner
5. Trade Journal with P&L
6. Daily Checklist
7. AI Analysis (GPT-4o)
8. Position Calculator
9. Alerts System
10. Backtest Results (manual + API + display)
11. Performance Dashboard (equity curve, stats, recent signals)
12. Subscriber System (Free/Pro/Elite + Stripe checkout)
13. Discord Branded Bot ("MNQ SCALP STACKS BOT" with 3-Pillar Setup)

## Configured
- Discord Webhook: LIVE (connected)
- Stripe: Test key (sk_test_emergent)
- Discord Invites: Placeholders (update in .env)

## Backlog
- P0: Connect TradingView, configure Discord invites, 48hr stress test
- P1: WebSocket, email sequences, Stripe subscription management, tier routing
- P2: Referral system, broker integration, mobile optimization
