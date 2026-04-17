# Trading Command Center - PRD

## Original Problem Statement
Build a trading dashboard for MNQ (Micro Nasdaq futures) scalping + $1-$20 stocks with high upside. Dual-engine system:
1. **Income Engine**: MNQ intraday scalping
2. **Growth Engine**: Stocks between $1-$20 for 2x-5x runners

## User Persona
- Active trader with limited time
- Focus on 9:30-10:30 AM or 3:00-4:00 PM trading sessions
- Max 2-3 trades per day
- Risk model: $20-$40 max per trade

## Core Requirements
- Real-time MNQ futures tracking with technical indicators
- Stock scanner for breakouts/unusual volume
- Watchlist management
- Trade journal with P&L tracking
- Daily trading checklist
- AI-powered trade analysis
- Alerts system

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, Recharts, Lucide Icons
- **Backend**: FastAPI, MongoDB, Motor
- **AI**: OpenAI GPT-4o via Emergent LLM Key
- **Data**: Alpha Vantage API (demo/free tier with mock fallback)

## What's Been Implemented (Jan 2026)

### Backend APIs
- ✅ `/api/futures/mnq` - MNQ data with VWAP, EMA9, EMA21, RSI
- ✅ `/api/watchlist` - CRUD operations
- ✅ `/api/stocks/quote/{symbol}` - Real-time quotes
- ✅ `/api/stocks/scanner` - Breakout detection
- ✅ `/api/trades` - Trade journal CRUD with P&L calculation
- ✅ `/api/trades/stats` - Win rate, avg win/loss
- ✅ `/api/checklist` - Daily checklist management
- ✅ `/api/alerts` - Price alerts
- ✅ `/api/ai/analyze` - GPT-4o powered analysis

### Frontend Components
- ✅ MNQ Futures Panel - Live indicators, bullish/bearish signal
- ✅ Watchlist - 5 stocks (SOFI, NIO, RKLB, PLUG, SNAP)
- ✅ Stock Scanner - Find breakouts
- ✅ Trade Journal - Log trades, close with P&L
- ✅ Daily Checklist - Pre-market, rules, post-market items
- ✅ AI Analysis - Entry/exit signals, sentiment
- ✅ Alerts Panel - Price target alerts

### Design
- Dark "Control Room" theme
- JetBrains Mono for data
- Neon glow effects for price changes
- Dense data layout

## Prioritized Backlog

### P0 (Next Session)
- [ ] Persist user preferences (dark/light mode)
- [ ] Real-time WebSocket for price updates

### P1
- [ ] TradingView chart integration
- [ ] Mobile responsive improvements
- [ ] Historical P&L charts
- [ ] Export trade journal to CSV

### P2
- [ ] Multi-user authentication
- [ ] Push notifications for alerts
- [ ] Backtesting module
- [ ] Integration with brokerage APIs

## Notes
- Alpha Vantage demo key has limited requests (25/day)
- Mock data activates when API limits reached
- MNQ uses QQQ as proxy scaled by 45x
