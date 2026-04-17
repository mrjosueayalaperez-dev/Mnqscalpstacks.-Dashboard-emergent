# Trading Command Center - PRD

## Original Problem Statement
Build a trading dashboard for MNQ (Micro Nasdaq futures) scalping + $1-$20 stocks. Dual-engine system with Signal Engine brain and public performance dashboard for subscriber conversion.

## Architecture
- **Frontend**: React 19, Tailwind CSS, Recharts, Sonner, Lucide Icons, React Router
- **Backend**: FastAPI, MongoDB (Motor), httpx
- **AI**: OpenAI GPT-4o via Emergent LLM Key
- **Data**: Alpha Vantage API (demo/free tier with mock fallback)
- **Signals**: TradingView webhook -> Backend -> Discord + Dashboard
- **Routes**: `/` (main dashboard), `/performance` (public page)

## What's Been Implemented

### Phase 1 - MVP Dashboard (Jan 2026)
- MNQ Futures Tracker (VWAP, EMA9, EMA21, RSI, Bullish/Bearish signal)
- Stock Watchlist (SOFI, NIO, RKLB, PLUG, SNAP)
- Stock Scanner (breakout/breakdown detection)
- Trade Journal with P&L calculation
- Daily Checklist (pre-market, rules, post-market)
- AI Analysis (GPT-4o powered)
- Alerts System
- Position Sizing Calculator (stocks + MNQ)

### Phase 2 - Signal Engine (Jan 2026)
- TradingView Webhook Receiver
- MNQ Stack Confluence Scoring (key levels + rejection + momentum + trend)
- Signal History with win/loss tracking
- Discord webhook delivery (placeholder URL)
- Kill Switch (manual + auto at >5% error rate)
- System Health monitoring
- Test Signal Generator
- Pine Script reference + TradingView setup instructions

### Phase 3 - Public Performance Dashboard (Jan 2026)
- `/performance` route - shareable public page
- Hero Stats (win rate, total P&L, avg R:R, best streak)
- Equity Curve chart (Recharts AreaChart)
- Win/Loss distribution bar
- Detailed metrics panel
- Recent signals feed (read-only, last 15)
- Demo data seeder (30 days, ~69% win rate)
- Navigation between dashboard and performance page

## Mocked/Placeholder Items
- **Discord Webhook**: Placeholder in `.env` — user to configure
- **Alpha Vantage**: Demo key with mock fallback
- **Demo Signals**: 63 pre-seeded signals for performance display
- **Test Signals**: Randomized, not from real market data

## All API Endpoints
- `/api/futures/mnq` - MNQ data
- `/api/stocks/quote/{symbol}` - Stock quotes
- `/api/stocks/scanner` - Breakout scanner
- `/api/watchlist` - Watchlist CRUD
- `/api/trades` - Trade journal CRUD
- `/api/trades/stats` - Trade statistics
- `/api/checklist` - Daily checklist
- `/api/alerts` - Alerts CRUD
- `/api/ai/analyze` - AI trade analysis
- `/api/calculator/position-size` - Position calculator
- `/api/calculator/mnq-position` - MNQ position calculator
- `/api/webhook/tradingview` - TradingView webhook receiver
- `/api/signals` - Signal history
- `/api/signals/stats` - Signal performance
- `/api/signals/health` - System health
- `/api/signals/kill-switch` - Kill switch
- `/api/signals/test` - Test signal generator
- `/api/signals/pinescript` - Pine Script code
- `/api/public/performance` - Public performance data
- `/api/public/seed-demo` - Seed demo signals

## Prioritized Backlog

### P0
- [ ] User configures real Discord webhook URL
- [ ] Connect TradingView with Pine Script indicator
- [ ] 48-hour stress test period

### P1
- [ ] WebSocket for real-time signal push
- [ ] User tier routing (beta/pro/elite)
- [ ] Referral/affiliate system
- [ ] Custom domain for /performance page

### P2
- [ ] Broker integration (Tradovate)
- [ ] Mobile responsive optimization
- [ ] Email notifications
- [ ] Backtesting module
