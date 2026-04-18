# Trading Command Center - PRD

## Original Problem Statement
Build a trading dashboard for MNQ futures scalping + $1-$20 stocks. Signal Engine v2 with Session VWAP + Structure logic, public performance dashboard, and subscriber monetization via Stripe.

## Architecture
- **Frontend**: React 19, Tailwind CSS, Recharts, React Router, Sonner
- **Backend**: FastAPI, MongoDB, Motor, httpx
- **AI**: OpenAI GPT-4o via Emergent LLM Key
- **Data**: Alpha Vantage API (demo key with mock fallback)
- **Signals**: TradingView webhook -> Backend -> Discord + Dashboard
- **Payments**: Stripe Checkout (test mode)
- **Routes**: `/` (main dashboard), `/performance` (public page + pricing)

## What's Been Implemented

### Phase 1 - MVP Dashboard
- MNQ Futures Tracker, Stock Watchlist, Scanner, Trade Journal, Daily Checklist, AI Analysis, Alerts, Position Calculator

### Phase 2 - Signal Engine v1
- Webhook receiver, kill switch, health monitoring, test generator

### Phase 3 - Public Performance Dashboard
- Equity curve chart, hero stats, win/loss distribution, recent signals

### Phase 4 - Subscriber System + Stripe
- Pricing tiers (Free/$0, Pro/$49, Elite/$149), email signup, Stripe checkout

### Phase 5 - Signal Engine v2 Upgrade
- **Pine Script**: Full v2 strategy — Session VWAP + Structure (higher-low / lower-high pivots)
- **Backend Confluence**: VWAP filter + RSI momentum + Structure confirmation (3-component scoring)
- **TP/SL**: Pivot-based (confirmed swing highs/lows, variable 6-15pt distances)
- **Test Signals**: v2 components (vwap_filter, rsi_momentum, structure)
- **Backward compatible**: Old v1 signals still visible in history

## Mocked/Placeholder Items
- Discord Webhook/Invites: Placeholders
- Alpha Vantage: Demo key
- Stripe: Test key
- Demo Signals: 63+ seeded

## Prioritized Backlog
### P0: Configure Discord + connect TradingView + 48hr stress test
### P1: WebSocket push, email sequences, Stripe subscription management, tier routing
### P2: Referral system, broker integration, mobile optimization, backtesting
