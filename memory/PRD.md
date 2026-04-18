# Trading Command Center - Final PRD

## System Overview
Full-stack MNQ futures scalping + $1-$20 stock trading system with Signal Engine v2, public performance dashboard, subscriber monetization, and backtesting.

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, Recharts, React Router, Sonner, Lucide
- **Backend**: FastAPI, MongoDB (Motor), httpx
- **AI**: OpenAI GPT-4o (Emergent LLM Key)
- **Data**: Alpha Vantage (demo key + mock fallback)
- **Signals**: TradingView webhook -> Backend -> Discord + Dashboard
- **Payments**: Stripe Checkout (test mode)

## Pages
- `/` — Main Trading Dashboard (all widgets)
- `/performance` — Public Performance Page (shareable, subscriber conversion)

## All Features Implemented

### Dashboard Widgets
1. MNQ Futures Tracker (VWAP, EMA9, EMA21, RSI, setup signal)
2. Signal Engine v2 (VWAP + RSI + Structure confluence, test generator, kill switch, health)
3. Watchlist (SOFI, NIO, RKLB, PLUG, SNAP with live quotes)
4. Stock Scanner (breakout/breakdown detection)
5. Trade Journal (CRUD, P&L calculation, win rate stats)
6. Daily Checklist (pre-market, rules, post-market)
7. AI Analysis (GPT-4o trade analysis, entry/exit signals)
8. Alerts (price targets, VWAP crosses)
9. Position Calculator (stocks + MNQ futures)
10. Backtest Manager (manual input form, CRUD, display)

### Signal Engine v2
- Pine Script: Session VWAP + Structure (pivots, higher-low/lower-high)
- Webhook: `/api/webhook/tradingview`
- Confluence: VWAP filter + RSI momentum + Structure (3-score)
- TP/SL: Pivot-based (variable swing distances)
- Kill Switch (manual + auto >5% error rate)
- Discord delivery, health monitoring, duplicate detection

### Performance Page
- Hero Stats (win rate, P&L, R:R, best streak)
- Equity Curve chart (30-day Recharts)
- Win/Loss distribution bar
- Recent Signals feed
- Verified Backtest display (profit factor, Sharpe, max DD, net profit)
- Pricing tiers (Free/$0, Pro/$49, Elite/$149)
- Email signup + Stripe checkout
- Post-payment Discord invite

## Placeholders to Configure
- `DISCORD_WEBHOOK_URL` — real webhook
- `DISCORD_INVITE_FREE/PRO/ELITE` — real invite links
- `STRIPE_API_KEY` — live key when ready
- `ALPHA_VANTAGE_KEY` — paid key for more API calls

## Backlog
- P0: Connect TradingView, configure Discord, 48hr stress test
- P1: WebSocket push, email sequences, Stripe subscription management
- P2: Referral system, broker integration (Tradovate), mobile optimization
