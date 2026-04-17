# Trading Command Center - PRD

## Original Problem Statement
Build a trading dashboard for MNQ futures scalping + $1-$20 stocks. Signal Engine brain with public performance dashboard and subscriber monetization via Stripe.

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
- MNQ Futures Tracker (VWAP, EMA9, EMA21, RSI, setup signal)
- Stock Watchlist (SOFI, NIO, RKLB, PLUG, SNAP)
- Stock Scanner (breakout/breakdown detection)
- Trade Journal with P&L calculation
- Daily Checklist (pre-market, rules, post-market)
- AI Analysis (GPT-4o powered)
- Alerts System
- Position Sizing Calculator (stocks + MNQ)

### Phase 2 - Signal Engine
- TradingView Webhook Receiver
- MNQ Stack Confluence Scoring
- Signal History with win/loss tracking
- Discord webhook delivery
- Kill Switch (manual + auto at >5% error rate)
- System Health monitoring
- Test Signal Generator
- Pine Script reference + TradingView setup

### Phase 3 - Public Performance Dashboard
- `/performance` route - shareable public page
- Hero Stats (win rate, P&L, R:R, best streak)
- Equity Curve chart (Recharts)
- Win/Loss distribution bar
- Recent signals feed

### Phase 4 - Subscriber System + Stripe
- Pricing tiers: Free ($0), Pro ($49/mo), Elite ($149/mo)
- Email signup form with tier selector
- Stripe Checkout integration for paid tiers
- Payment transaction tracking in MongoDB
- Discord invite links after signup (placeholder)
- Subscriber count display
- Post-payment success panel
- Idempotent email handling

## Mocked/Placeholder Items
- **Discord Webhook**: Placeholder in `.env`
- **Discord Invites**: Placeholder URLs for each tier
- **Alpha Vantage**: Demo key with mock fallback
- **Stripe**: Test key (sk_test_emergent)
- **Demo Signals**: 63+ pre-seeded signals

## Prioritized Backlog

### P0
- [ ] Configure real Discord webhook + invite URLs
- [ ] Connect TradingView with Pine Script
- [ ] 48-hour stress test

### P1
- [ ] WebSocket for real-time signal push
- [ ] Email welcome sequences (SendGrid)
- [ ] Stripe subscription management (cancel/upgrade)
- [ ] User tier routing (beta/pro/elite signal filtering)

### P2
- [ ] Referral/affiliate system
- [ ] Broker integration (Tradovate)
- [ ] Mobile responsive optimization
- [ ] Backtesting module
