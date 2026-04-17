# Trading Command Center - PRD

## Original Problem Statement
Build a trading dashboard for MNQ (Micro Nasdaq futures) scalping + $1-$20 stocks with high upside. Dual-engine system with Signal Engine brain.

## Architecture
- **Frontend**: React 19, Tailwind CSS, Sonner toasts, Lucide Icons
- **Backend**: FastAPI, MongoDB (Motor), httpx
- **AI**: OpenAI GPT-4o via Emergent LLM Key
- **Data**: Alpha Vantage API (demo/free tier with mock fallback)
- **Signals**: TradingView webhook → Backend → Discord + Dashboard

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
- TradingView Webhook Receiver (`/api/webhook/tradingview`)
- MNQ Stack Confluence Scoring (key levels + rejection + momentum + trend)
- Signal History with win/loss tracking
- Discord webhook delivery (placeholder URL, user to configure)
- Kill Switch (manual + auto at >5% error rate)
- System Health monitoring
- Test Signal Generator
- Pine Script reference + TradingView setup instructions
- Signal performance metrics (win rate, avg R:R, frequency)

## Mocked/Placeholder Items
- **Discord Webhook**: Placeholder URL in `.env` — user needs to replace with real URL
- **Alpha Vantage**: Demo key with mock fallback when rate limited
- **Test Signals**: Randomized, not from real market data

## API Endpoints
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

## Prioritized Backlog

### P0
- [ ] User configures real Discord webhook URL
- [ ] Connect TradingView with Pine Script indicator

### P1
- [ ] WebSocket for real-time signal push
- [ ] Historical P&L charts (Recharts)
- [ ] Multi-user auth + tier routing (beta/pro/elite)
- [ ] Signal duplication window tuning

### P2
- [ ] Referral/affiliate system
- [ ] Public performance dashboard
- [ ] Broker integration (Tradovate)
- [ ] Mobile responsive optimization
