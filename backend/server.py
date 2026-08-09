from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Request, WebSocket, WebSocketDisconnect, Depends, Header
from fastapi.responses import RedirectResponse
from market_feed import broker as tick_broker, refresh_once as refresh_mnq, get_last as get_last_mnq
from market_context import get_market_context
import ati
import proof
import auth as auth_module
import analytics
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone, timedelta
import httpx
import secrets
import hashlib
from emergentintegrations.llm.chat import LlmChat, UserMessage

# Secure random generator
_rng = secrets.SystemRandom()

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
client = AsyncIOMotorClient(mongo_url, serverSelectionTimeoutMS=5000)
db = client[os.environ.get('DB_NAME', 'test_database')]

# API Keys
ALPHA_VANTAGE_KEY = os.environ.get('ALPHA_VANTAGE_KEY', 'demo')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', '')
STRIPE_API_KEY = os.environ.get('STRIPE_API_KEY', '')

# Subscription tiers
SUBSCRIPTION_TIERS = {
    "free": {"name": "Free", "price": 0.0, "discord_env": "DISCORD_INVITE_FREE"},
    "pro": {"name": "Pro", "price": 49.00, "discord_env": "DISCORD_INVITE_PRO"},
    "elite": {"name": "Elite", "price": 149.00, "discord_env": "DISCORD_INVITE_ELITE"},
}

# Discord invite links
DISCORD_INVITES = {
    "free": os.environ.get("DISCORD_INVITE_FREE", ""),
    "pro": os.environ.get("DISCORD_INVITE_PRO", ""),
    "elite": os.environ.get("DISCORD_INVITE_ELITE", ""),
}

# Affiliate / partner outbound URLs (revenue tracking)
AFFILIATE_URLS = {
    "ninjatrader": os.environ.get("AFFILIATE_URL_NINJATRADER", "https://ninjatrader.com/"),
    "tradingview": os.environ.get("AFFILIATE_URL_TRADINGVIEW", "https://www.tradingview.com/"),
    "gpay": os.environ.get("AFFILIATE_URL_GPAY", "https://pay.google.com/"),
    "discord": os.environ.get("AFFILIATE_URL_DISCORD", "https://discord.com/"),
}

# Signal Engine State (in-memory for fast access)
signal_engine_state = {
    "kill_switch": False,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "total_signals": 0,
    "errors": 0,
    "last_signal_time": None,
    "last_error": None,
}

# Create the main app with a proper title (drives the OpenAPI spec Retool consumes)
app = FastAPI(
    title="MNQ Scalp Stacks API",
    description="Operator cockpit + subscriber/admin/market backend. Retool-ready.",
    version="1.5.0",
    openapi_url="/api/openapi.json",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=[
        {"name": "operator", "description": "Personal trading cockpit (orders, state, journal, controls)."},
        {"name": "market",   "description": "Live MNQ feed + multi-day context."},
        {"name": "signals",  "description": "Signal engine, TradingView webhooks, Pine script."},
        {"name": "admin",    "description": "Subscriber management + affiliate revenue."},
        {"name": "public",   "description": "Public performance / leaderboard / referrals."},
        {"name": "ati",      "description": "NinjaTrader ATI bridge (Phase 2 real order routing)."},
    ],
)
api_router = APIRouter(prefix="/api")

# ---- Retool integration guard ----
# Retool + any other write client must present X-API-Key on state-mutating endpoints.
# Reads (GET) stay open so the public site / Retool dashboards can display data
# without needing keys. Configure via env: RETOOL_API_KEY=<any long random string>.
RETOOL_API_KEY = os.environ.get("RETOOL_API_KEY", "")


def require_write_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
    """FastAPI dependency: enforced on every mutating endpoint. If RETOOL_API_KEY
    is unset (dev/preview default), this is a no-op — the endpoint is open.
    Set the env var in production to lock all writes to Retool + your own tools."""
    if not RETOOL_API_KEY:
        return
    if x_api_key != RETOOL_API_KEY:
        raise HTTPException(status_code=401, detail="Missing or invalid X-API-Key header")

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== Models ==============

class WatchlistItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    name: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None
    category: str = "stock"  # stock, futures
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WatchlistItemCreate(BaseModel):
    symbol: str
    name: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    notes: Optional[str] = None
    category: str = "stock"

class TradeEntry(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    entry_price: float
    exit_price: Optional[float] = None
    quantity: int
    side: str  # long, short
    status: str = "open"  # open, closed
    entry_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    exit_date: Optional[datetime] = None
    pnl: Optional[float] = None
    notes: Optional[str] = None

class TradeEntryCreate(BaseModel):
    symbol: str
    entry_price: float
    quantity: int
    side: str
    notes: Optional[str] = None

class TradeEntryUpdate(BaseModel):
    exit_price: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None

class ChecklistItem(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    text: str
    completed: bool = False
    category: str = "premarket"  # premarket, rules, postmarket
    order: int = 0

class ChecklistItemCreate(BaseModel):
    text: str
    category: str = "premarket"
    order: int = 0

class Alert(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str
    alert_type: str  # breakout, vwap_cross, price_target, stop_loss
    condition: str
    target_value: float
    triggered: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AlertCreate(BaseModel):
    symbol: str
    alert_type: str
    condition: str
    target_value: float

class AIAnalysisRequest(BaseModel):
    symbol: str
    context: Optional[str] = None
    analysis_type: str = "general"  # general, entry, exit, sentiment

class PositionSizeRequest(BaseModel):
    entry_price: float
    stop_loss: float
    risk_amount: float = 30.0  # Default $30 risk (middle of $20-$40 range)
    account_balance: Optional[float] = None

class PositionSizeResponse(BaseModel):
    entry_price: float
    stop_loss: float
    risk_amount: float
    risk_per_share: float
    position_size: int
    total_position_value: float
    target_1r: float  # 1:1 risk-reward
    target_2r: float  # 1:2 risk-reward
    max_loss: float
    potential_profit_1r: float
    potential_profit_2r: float

# ============== Signal Engine Models ==============

class TradingViewWebhook(BaseModel):
    type: Optional[str] = None  # buy, sell
    symbol: Optional[str] = "MNQ"
    price: Optional[str] = None
    time: Optional[str] = None

class Signal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    symbol: str = "MNQ"
    side: str  # long, short
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    confluence_score: int = 0
    components: Dict[str, bool] = {}
    trend_direction: str = "neutral"
    status: str = "active"  # active, hit_tp1, hit_tp2, stopped, expired
    outcome: Optional[str] = None  # win, loss, breakeven
    pnl_points: Optional[float] = None
    discord_sent: bool = False
    source: str = "engine"  # engine, webhook, test
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = None

class SubscriberCreate(BaseModel):
    email: str
    name: Optional[str] = None
    tier: str = "free"  # free, pro, elite
    referral_code: Optional[str] = None  # Code used during signup

class CheckoutRequest(BaseModel):
    tier: str  # pro, elite
    origin_url: str
    email: str = ""  # logged-in user's email for auto tier upgrade

class BacktestResult(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_name: str = "MNQ Scalp Stack v2"
    timeframe: str = "1m"
    symbol: str = "MNQ"
    period_start: str = ""
    period_end: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    net_profit: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    avg_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    notes: Optional[str] = None
    is_verified: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class BacktestCreate(BaseModel):
    strategy_name: str = "MNQ Scalp Stack v2"
    timeframe: str = "1m"
    symbol: str = "MNQ"
    period_start: str = ""
    period_end: str = ""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    profit_factor: float = 0.0
    net_profit: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_pct: float = 0.0
    sharpe_ratio: float = 0.0
    avg_trade: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    largest_win: float = 0.0
    largest_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    notes: Optional[str] = None

# ============== Signal Engine Functions ==============

def _discord_webhook_configured() -> bool:
    return bool(DISCORD_WEBHOOK_URL) and DISCORD_WEBHOOK_URL != "REPLACE_WITH_YOUR_DISCORD_WEBHOOK_URL"


def _format_signal_pillars(components: dict) -> str:
    pillars = []
    if components.get("ema21_cross"):
        pillars.append("EMA21 Cross")
    if components.get("vwap_filter"):
        pillars.append("VWAP")
    if not pillars:
        pillars = ["EMA21", "VWAP"]
    return " + ".join(pillars) + " Confirmed"


def _rr_ratio(entry: float, stop: float, tp1: float) -> str:
    risk = abs(entry - stop)
    if risk <= 0:
        return "N/A"
    return f"{abs(tp1 - entry) / risk:.1f}:1"


def _build_discord_payload(signal: dict) -> dict:
    is_long = signal["side"] == "long"
    side_label = "LONG" if is_long else "SHORT"
    side_emoji = "🟢" if is_long else "🔴"
    signal_color = 5763719 if is_long else 15548997  # Green / Red

    pillar_status = _format_signal_pillars(signal.get("components", {}))
    score = signal.get("confluence_score", 0)

    entry = signal.get("entry_price", 0)
    stop = signal.get("stop_loss", 0)
    tp1 = signal.get("tp1", 0)
    rr = _rr_ratio(entry, stop, tp1)

    return {
        "username": "MNQ SCALP STACKS BOT",
        "avatar_url": "https://i.imgur.com/4S7S5vj.png",
        "embeds": [{
            "title": f"{side_emoji} SCALP PUNCH — {side_label}",
            "color": signal_color,
            "fields": [
                {"name": "Asset", "value": "MNQ (Micro Nasdaq)", "inline": True},
                {"name": "Strategy", "value": f"Scalp Punch ({score}/2)", "inline": True},
                {"name": "Status", "value": f"{'✅' if score >= 2 else '⚠️'} {pillar_status}", "inline": False},
                {"name": "Entry", "value": f"```${entry:.2f}```", "inline": True},
                {"name": "Stop Loss", "value": f"```${stop:.2f}```", "inline": True},
                {"name": "R:R", "value": f"```{rr}```", "inline": True},
                {"name": "TP1", "value": f"```${tp1:.2f}```", "inline": True},
                {"name": "TP2", "value": f"```${signal.get('tp2', 0):.2f}```", "inline": True},
                {"name": "Trend", "value": f"```{signal.get('trend_direction', 'neutral').upper()}```", "inline": True},
            ],
            "footer": {"text": "MNQ SCALP STACKS SaaS | Emergent.sh"},
            "timestamp": signal.get("created_at", datetime.now(timezone.utc).isoformat()),
        }],
    }


async def send_discord_signal(signal: dict) -> bool:
    """Send branded signal to Discord webhook — MNQ SCALP STACKS BOT."""
    if not _discord_webhook_configured():
        logger.info("Discord webhook not configured, skipping delivery")
        return False
    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.post(DISCORD_WEBHOOK_URL, json=_build_discord_payload(signal), timeout=5.0)
            return resp.status_code in (200, 204)
    except Exception as e:
        logger.error(f"Discord send failed: {e}")
        return False


async def check_duplicate_signal(symbol: str, side: str, minutes: int = 5) -> bool:
    """Check if a similar signal was already sent recently"""
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
    existing = await db.signals.find_one({
        "symbol": symbol,
        "side": side,
        "created_at": {"$gte": cutoff},
        "status": "active"
    })
    return existing is not None


def compute_confluence(price: float, prev_high: float, prev_low: float,
                       open_price: float, close_price: float,
                       high_price: float, low_price: float,
                       ema20: float, ema50: float) -> dict:
    """Compute MNQ Scalp Punch confluence
    BUY Punch: Price crosses above EMA21 + Price > VWAP
    SELL Punch: Price crosses below EMA21 + Price < VWAP
    """
    ema21 = ema20  # Using ema20 as proxy for EMA21
    vwap = ema50   # Using ema50 as proxy for VWAP

    # EMA21 crossover detection
    ema21_cross_above = close_price > ema21 and open_price <= ema21
    ema21_cross_below = close_price < ema21 and open_price >= ema21

    # VWAP filter
    above_vwap = close_price > vwap
    below_vwap = close_price < vwap

    # Scalp Punch signals
    buy_punch = ema21_cross_above and above_vwap
    sell_punch = ema21_cross_below and below_vwap

    # Score: EMA21 cross + VWAP confirmation
    long_score = int(ema21_cross_above) + int(above_vwap)
    short_score = int(ema21_cross_below) + int(below_vwap)

    return {
        "ema21_cross_above": ema21_cross_above,
        "ema21_cross_below": ema21_cross_below,
        "above_vwap": above_vwap,
        "below_vwap": below_vwap,
        "long_score": long_score,
        "short_score": short_score,
        "long_signal": buy_punch,
        "short_signal": sell_punch,
        "trend_direction": "bullish" if above_vwap else ("bearish" if below_vwap else "neutral"),
    }

# ============== Stock Data Functions ==============

async def fetch_stock_quote(symbol: str) -> Dict[str, Any]:
    """Fetch real-time stock quote from Alpha Vantage"""
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={ALPHA_VANTAGE_KEY}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            
            if "Global Quote" in data and data["Global Quote"]:
                quote = data["Global Quote"]
                return {
                    "symbol": quote.get("01. symbol", symbol),
                    "price": float(quote.get("05. price", 0)),
                    "change": float(quote.get("09. change", 0)),
                    "change_percent": quote.get("10. change percent", "0%").replace("%", ""),
                    "volume": int(quote.get("06. volume", 0)),
                    "high": float(quote.get("03. high", 0)),
                    "low": float(quote.get("04. low", 0)),
                    "open": float(quote.get("02. open", 0)),
                    "previous_close": float(quote.get("08. previous close", 0)),
                }
            return None
        except Exception as e:
            logger.error(f"Error fetching quote for {symbol}: {e}")
            return None

async def fetch_intraday_data(symbol: str) -> List[Dict]:
    """Fetch intraday data for charts"""
    async with httpx.AsyncClient() as client:
        try:
            url = f"https://www.alphavantage.co/query?function=TIME_SERIES_INTRADAY&symbol={symbol}&interval=5min&apikey={ALPHA_VANTAGE_KEY}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            
            if "Time Series (5min)" in data:
                series = data["Time Series (5min)"]
                result = []
                for timestamp, values in list(series.items())[:50]:
                    result.append({
                        "time": timestamp,
                        "open": float(values["1. open"]),
                        "high": float(values["2. high"]),
                        "low": float(values["3. low"]),
                        "close": float(values["4. close"]),
                        "volume": int(values["5. volume"])
                    })
                return list(reversed(result))
            return []
        except Exception as e:
            logger.error(f"Error fetching intraday for {symbol}: {e}")
            return []

async def fetch_technical_indicators(symbol: str) -> Dict[str, Any]:
    """Fetch technical indicators - EMA, RSI"""
    indicators = {}
    async with httpx.AsyncClient() as client:
        try:
            # EMA 9
            url = f"https://www.alphavantage.co/query?function=EMA&symbol={symbol}&interval=5min&time_period=9&series_type=close&apikey={ALPHA_VANTAGE_KEY}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            if "Technical Analysis: EMA" in data:
                ema_data = list(data["Technical Analysis: EMA"].values())[:1]
                if ema_data:
                    indicators["ema9"] = float(ema_data[0]["EMA"])
            
            # EMA 21
            url = f"https://www.alphavantage.co/query?function=EMA&symbol={symbol}&interval=5min&time_period=21&series_type=close&apikey={ALPHA_VANTAGE_KEY}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            if "Technical Analysis: EMA" in data:
                ema_data = list(data["Technical Analysis: EMA"].values())[:1]
                if ema_data:
                    indicators["ema21"] = float(ema_data[0]["EMA"])
            
            # RSI
            url = f"https://www.alphavantage.co/query?function=RSI&symbol={symbol}&interval=5min&time_period=14&series_type=close&apikey={ALPHA_VANTAGE_KEY}"
            response = await client.get(url, timeout=10.0)
            data = response.json()
            if "Technical Analysis: RSI" in data:
                rsi_data = list(data["Technical Analysis: RSI"].values())[:1]
                if rsi_data:
                    indicators["rsi"] = float(rsi_data[0]["RSI"])
                    
        except Exception as e:
            logger.error(f"Error fetching indicators for {symbol}: {e}")
    
    return indicators

# ============== API Routes ==============

@api_router.get("/")
async def root():
    return {"message": "Trading Command Center API"}

# Stock Data Routes
@api_router.get("/stocks/quote/{symbol}")
async def get_stock_quote(symbol: str):
    """Get real-time quote for a stock"""
    quote = await fetch_stock_quote(symbol.upper())
    if not quote:
        # Return mock data when API limit reached
        return {
            "symbol": symbol.upper(),
            "price": 150.00 + (hash(symbol) % 100),
            "change": 2.50,
            "change_percent": "1.67",
            "volume": 1500000,
            "high": 152.00,
            "low": 148.00,
            "open": 149.00,
            "previous_close": 147.50,
            "is_mock": True
        }
    return quote

@api_router.get("/stocks/intraday/{symbol}")
async def get_intraday(symbol: str):
    """Get intraday price data"""
    data = await fetch_intraday_data(symbol.upper())
    if not data:
        # Generate mock intraday data
        base_price = 150 + (hash(symbol) % 50)
        mock_data = []
        for i in range(50):
            price = base_price + _rng.uniform(-5, 5)
            mock_data.append({
                "time": f"2024-01-15 {9 + i//12}:{(i*5) % 60:02d}:00",
                "open": price,
                "high": price + _rng.uniform(0, 2),
                "low": price - _rng.uniform(0, 2),
                "close": price + _rng.uniform(-1, 1),
                "volume": _rng.randint(10000, 100000)
            })
        return {"data": mock_data, "is_mock": True}
    return {"data": data}

@api_router.get("/stocks/indicators/{symbol}")
async def get_indicators(symbol: str):
    """Get technical indicators"""
    indicators = await fetch_technical_indicators(symbol.upper())
    if not indicators:
        # Return mock indicators
        base = 150 + (hash(symbol) % 50)
        return {
            "ema9": base + 1.5,
            "ema21": base - 0.5,
            "rsi": 55 + (hash(symbol) % 20),
            "vwap": base + 0.8,
            "is_mock": True
        }
    # Add VWAP (simplified calculation)
    indicators["vwap"] = indicators.get("ema9", 0) * 0.995
    return indicators

@api_router.get("/stocks/scanner")
async def scan_stocks(min_change: float = 3.0):
    """Scan for stocks with unusual activity"""
    # Default watchlist stocks
    symbols = ["SOFI", "NIO", "RKLB", "PLUG", "SNAP", "F", "OPEN", "AMD", "PLTR", "RIVN"]
    results = []
    
    for symbol in symbols[:5]:  # Limit to conserve API calls
        quote = await fetch_stock_quote(symbol)
        if quote:
            change_pct = float(quote.get("change_percent", "0").replace("%", ""))
            if abs(change_pct) >= min_change:
                results.append({
                    **quote,
                    "alert_type": "breakout" if change_pct > 0 else "breakdown"
                })
    
    # Add some mock results if no real results
    if not results:
        for symbol in symbols[:3]:
            change = _rng.uniform(3, 8) * (1 if _rng.random() > 0.5 else -1)
            results.append({
                "symbol": symbol,
                "price": 10 + (hash(symbol) % 20),
                "change": round(change * 0.1, 2),
                "change_percent": str(round(change, 2)),
                "volume": _rng.randint(500000, 5000000),
                "alert_type": "breakout" if change > 0 else "breakdown",
                "is_mock": True
            })
    
    return {"scanners": results}

# MNQ Futures Routes — LIVE feed (CME via Yahoo NQ=F; NQ and MNQ trade at same price)
@api_router.get("/futures/mnq", tags=["market"])
async def get_mnq_data() -> Dict[str, Any]:
    """Real-time MNQ futures snapshot. Falls back to cached tick on transient errors."""
    snap = await refresh_mnq()
    if not snap.get("price"):
        # Empty cache + fetch failed — return last known good or hard fallback
        snap = get_last_mnq()
    return {
        "symbol": "MNQ",
        "price": snap.get("price", 0),
        "close": snap.get("close", snap.get("price", 0)),
        "previous_close": snap.get("previous_close", 0),
        "change": snap.get("change", 0),
        "change_percent": str(snap.get("change_percent", 0)),
        "high": snap.get("day_high", 0),
        "low": snap.get("day_low", 0),
        "vwap": snap.get("vwap", 0),
        "ema9": snap.get("ema9", 0),
        "ema21": snap.get("ema21", 0),
        "rsi": snap.get("rsi", 50),
        "data_source": snap.get("source", "yahoo:NQ=F"),
        "market_state": snap.get("market_state", "UNKNOWN"),
        "exchange": snap.get("exchange", "CME"),
        "stale": snap.get("stale", False),
        "fetched_at": snap.get("fetched_at", 0),
        "is_mock": False,
        "wave_valid": True,
    }


@app.websocket("/api/ws/mnq")
async def mnq_socket(ws: WebSocket):
    """Live MNQ tick stream (~3s cadence, server-side fan-out)."""
    await ws.accept()
    # Immediately send the cached snapshot so client gets instant data
    snap = get_last_mnq()
    if snap.get("price"):
        try:
            await ws.send_json(snap)
        except Exception:
            return
    tick_broker.register(ws)
    try:
        while True:
            # Keep the socket alive; we only need to listen for client disconnect
            msg = await ws.receive_text()
            if msg == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning(f"ws error: {e}")
    finally:
        tick_broker.unregister(ws)


# Multi-day market context (PDH/PDL, ADR, range expansion, trend)
@api_router.get("/market/context", tags=["market"])
async def market_context() -> Dict[str, Any]:
    ctx = await get_market_context()
    if not ctx:
        raise HTTPException(status_code=503, detail="Market context unavailable")
    return ctx


# Watchlist Routes
@api_router.get("/watchlist", response_model=List[WatchlistItem])
async def get_watchlist():
    """Get all watchlist items"""
    items = await db.watchlist.find({}, {"_id": 0}).to_list(100)
    for item in items:
        if isinstance(item.get('created_at'), str):
            item['created_at'] = datetime.fromisoformat(item['created_at'])
    return items

@api_router.post("/watchlist", response_model=WatchlistItem)
async def add_to_watchlist(item: WatchlistItemCreate):
    """Add item to watchlist"""
    watchlist_item = WatchlistItem(**item.model_dump())
    doc = watchlist_item.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.watchlist.insert_one(doc)
    return watchlist_item

@api_router.delete("/watchlist/{item_id}")
async def remove_from_watchlist(item_id: str):
    """Remove item from watchlist"""
    result = await db.watchlist.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Deleted"}

# Trade Journal Routes
@api_router.get("/trades", response_model=List[TradeEntry])
async def get_trades(status: Optional[str] = None):
    """Get all trades, optionally filtered by status"""
    query = {}
    if status:
        query["status"] = status
    trades = await db.trades.find(query, {"_id": 0}).to_list(100)
    for trade in trades:
        if isinstance(trade.get('entry_date'), str):
            trade['entry_date'] = datetime.fromisoformat(trade['entry_date'])
        if isinstance(trade.get('exit_date'), str):
            trade['exit_date'] = datetime.fromisoformat(trade['exit_date'])
    return trades

@api_router.post("/trades", response_model=TradeEntry)
async def create_trade(trade: TradeEntryCreate):
    """Create a new trade entry"""
    trade_entry = TradeEntry(**trade.model_dump())
    doc = trade_entry.model_dump()
    doc['entry_date'] = doc['entry_date'].isoformat()
    if doc['exit_date']:
        doc['exit_date'] = doc['exit_date'].isoformat()
    await db.trades.insert_one(doc)
    return trade_entry

@api_router.patch("/trades/{trade_id}", response_model=TradeEntry)
async def update_trade(trade_id: str, update: TradeEntryUpdate):
    """Update a trade (close it, add notes)"""
    existing = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Trade not found")
    
    update_data = update.model_dump(exclude_unset=True)
    
    if update_data.get("exit_price") and update_data.get("status") == "closed":
        entry_price = existing["entry_price"]
        quantity = existing["quantity"]
        side = existing["side"]
        exit_price = update_data["exit_price"]
        
        if side == "long":
            pnl = (exit_price - entry_price) * quantity
        else:
            pnl = (entry_price - exit_price) * quantity
        
        update_data["pnl"] = round(pnl, 2)
        update_data["exit_date"] = datetime.now(timezone.utc).isoformat()
    
    await db.trades.update_one({"id": trade_id}, {"$set": update_data})
    updated = await db.trades.find_one({"id": trade_id}, {"_id": 0})
    if isinstance(updated.get('entry_date'), str):
        updated['entry_date'] = datetime.fromisoformat(updated['entry_date'])
    if isinstance(updated.get('exit_date'), str):
        updated['exit_date'] = datetime.fromisoformat(updated['exit_date'])
    return updated

@api_router.get("/trades/stats")
async def get_trade_stats():
    """Get trading statistics"""
    trades = await db.trades.find({"status": "closed"}, {"_id": 0}).to_list(1000)
    
    if not trades:
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "avg_win": 0,
            "avg_loss": 0
        }
    
    total = len(trades)
    winners = [t for t in trades if t.get("pnl", 0) > 0]
    losers = [t for t in trades if t.get("pnl", 0) < 0]
    total_pnl = sum(t.get("pnl", 0) for t in trades)
    
    return {
        "total_trades": total,
        "winning_trades": len(winners),
        "losing_trades": len(losers),
        "win_rate": round(len(winners) / total * 100, 1) if total > 0 else 0,
        "total_pnl": round(total_pnl, 2),
        "avg_win": round(sum(t["pnl"] for t in winners) / len(winners), 2) if winners else 0,
        "avg_loss": round(sum(t["pnl"] for t in losers) / len(losers), 2) if losers else 0
    }

# Checklist Routes
@api_router.get("/checklist")
async def get_checklist():
    """Get all checklist items"""
    items = await db.checklist.find({}, {"_id": 0}).to_list(100)
    return items

@api_router.post("/checklist", response_model=ChecklistItem)
async def add_checklist_item(item: ChecklistItemCreate):
    """Add checklist item"""
    checklist_item = ChecklistItem(**item.model_dump())
    doc = checklist_item.model_dump()
    await db.checklist.insert_one(doc)
    return checklist_item

@api_router.patch("/checklist/{item_id}")
async def toggle_checklist(item_id: str, completed: bool):
    """Toggle checklist item completion"""
    result = await db.checklist.update_one(
        {"id": item_id}, 
        {"$set": {"completed": completed}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Updated"}

@api_router.delete("/checklist/{item_id}")
async def delete_checklist_item(item_id: str):
    """Delete checklist item"""
    result = await db.checklist.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"message": "Deleted"}

@api_router.post("/checklist/reset")
async def reset_checklist():
    """Reset all checklist items to uncompleted"""
    await db.checklist.update_many({}, {"$set": {"completed": False}})
    return {"message": "Reset complete"}

# Alerts Routes
@api_router.get("/alerts", response_model=List[Alert])
async def get_alerts():
    """Get all alerts"""
    alerts = await db.alerts.find({}, {"_id": 0}).to_list(100)
    for alert in alerts:
        if isinstance(alert.get('created_at'), str):
            alert['created_at'] = datetime.fromisoformat(alert['created_at'])
    return alerts

@api_router.post("/alerts", response_model=Alert)
async def create_alert(alert: AlertCreate):
    """Create a new alert"""
    alert_obj = Alert(**alert.model_dump())
    doc = alert_obj.model_dump()
    doc['created_at'] = doc['created_at'].isoformat()
    await db.alerts.insert_one(doc)
    return alert_obj

@api_router.delete("/alerts/{alert_id}")
async def delete_alert(alert_id: str):
    """Delete an alert"""
    result = await db.alerts.delete_one({"id": alert_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"message": "Deleted"}

# Position Sizing Calculator
@api_router.post("/calculator/position-size", response_model=PositionSizeResponse)
async def calculate_position_size(request: PositionSizeRequest):
    """Calculate optimal position size based on risk parameters"""
    entry = request.entry_price
    stop = request.stop_loss
    risk = request.risk_amount
    
    # Calculate risk per share (distance to stop loss)
    risk_per_share = abs(entry - stop)
    
    if risk_per_share == 0:
        raise HTTPException(status_code=400, detail="Stop loss cannot equal entry price")
    
    # Calculate position size (shares you can buy within risk tolerance)
    position_size = int(risk / risk_per_share)
    
    if position_size < 1:
        position_size = 1
    
    # Total position value
    total_value = position_size * entry
    
    # Calculate targets (1:1 and 1:2 risk-reward)
    is_long = entry > stop
    if is_long:
        target_1r = entry + risk_per_share
        target_2r = entry + (risk_per_share * 2)
    else:
        target_1r = entry - risk_per_share
        target_2r = entry - (risk_per_share * 2)
    
    # Calculate potential profits
    max_loss = position_size * risk_per_share
    potential_profit_1r = position_size * risk_per_share
    potential_profit_2r = position_size * risk_per_share * 2
    
    return PositionSizeResponse(
        entry_price=entry,
        stop_loss=stop,
        risk_amount=risk,
        risk_per_share=round(risk_per_share, 4),
        position_size=position_size,
        total_position_value=round(total_value, 2),
        target_1r=round(target_1r, 4),
        target_2r=round(target_2r, 4),
        max_loss=round(max_loss, 2),
        potential_profit_1r=round(potential_profit_1r, 2),
        potential_profit_2r=round(potential_profit_2r, 2)
    )

# MNQ Position Size (futures specific - $2 per point per contract)
@api_router.post("/calculator/mnq-position")
async def calculate_mnq_position(stop_points: int = 15, risk_amount: float = 30.0):
    """Calculate MNQ contracts based on stop loss points and risk"""
    # MNQ = $2 per point per contract
    dollar_per_point = 2.0
    risk_per_contract = stop_points * dollar_per_point
    
    contracts = int(risk_amount / risk_per_contract)
    if contracts < 1:
        contracts = 1
    
    actual_risk = contracts * risk_per_contract
    target_1r_profit = actual_risk
    target_2r_profit = actual_risk * 2
    
    return {
        "stop_points": stop_points,
        "risk_amount": risk_amount,
        "contracts": contracts,
        "actual_risk": round(actual_risk, 2),
        "target_points_1r": stop_points,
        "target_points_2r": stop_points * 2,
        "potential_profit_1r": round(target_1r_profit, 2),
        "potential_profit_2r": round(target_2r_profit, 2),
        "dollar_per_point": dollar_per_point
    }

# AI Analysis Routes
@api_router.post("/ai/analyze")
async def ai_analyze(request: AIAnalysisRequest):
    """Get AI-powered trade analysis"""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    # Fetch current data for the symbol
    quote = await fetch_stock_quote(request.symbol)
    indicators = await fetch_technical_indicators(request.symbol)
    
    # Handle None values safely
    price = quote.get('price', 'N/A') if quote else 'N/A'
    change_pct = quote.get('change_percent', 'N/A') if quote else 'N/A'
    volume = quote.get('volume', 'N/A') if quote else 'N/A'
    ema9 = indicators.get('ema9', 'N/A') if indicators else 'N/A'
    ema21 = indicators.get('ema21', 'N/A') if indicators else 'N/A'
    rsi = indicators.get('rsi', 'N/A') if indicators else 'N/A'
    
    system_message = """You are an expert trading analyst specializing in MNQ futures and momentum stocks ($1-$20 range). 
    Provide concise, actionable analysis. Focus on:
    - Entry/exit points based on technical indicators
    - Risk management (stop loss, position sizing)
    - Market context and momentum
    Be direct and specific. No financial advice disclaimers."""
    
    context_data = f"""
    Symbol: {request.symbol}
    Current Price: ${price}
    Change: {change_pct}%
    Volume: {volume}
    EMA 9: {ema9}
    EMA 21: {ema21}
    RSI (14): {rsi}
    """
    
    prompts = {
        "general": f"Analyze {request.symbol} for potential trading opportunity. {context_data}",
        "entry": f"Should I enter a position on {request.symbol}? Provide specific entry levels. {context_data}",
        "exit": f"I have a position in {request.symbol}. Should I exit? {context_data}",
        "sentiment": f"What's the market sentiment for {request.symbol}? {context_data}"
    }
    
    user_prompt = prompts.get(request.analysis_type, prompts["general"])
    if request.context:
        user_prompt += f"\nAdditional context: {request.context}"
    
    try:
        chat = LlmChat(
            api_key=EMERGENT_LLM_KEY,
            session_id=f"trade-analysis-{request.symbol}-{uuid.uuid4()}",
            system_message=system_message
        ).with_model("openai", "gpt-4o")
        
        response = await chat.send_message(UserMessage(text=user_prompt))
        
        return {
            "symbol": request.symbol,
            "analysis_type": request.analysis_type,
            "analysis": response,
            "data_used": {
                "quote": quote,
                "indicators": indicators
            }
        }
    except Exception as e:
        logger.error(f"AI analysis error: {e}")
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")

# ============== Signal Engine Routes ==============

# TradingView Webhook Receiver
@api_router.post("/webhook/tradingview")
async def receive_tradingview_webhook(payload: TradingViewWebhook, background_tasks: BackgroundTasks):
    """Receive signals from TradingView webhook"""
    if signal_engine_state["kill_switch"]:
        return {"status": "blocked", "reason": "Kill switch active"}

    # Check duplicate
    side = "long" if payload.type and payload.type.lower() == "buy" else "short"
    symbol = payload.symbol or "MNQ"
    is_dup = await check_duplicate_signal(symbol, side, minutes=3)
    if is_dup:
        signal_engine_state["errors"] += 1
        return {"status": "duplicate", "reason": "Signal already active"}

    price = float(payload.price) if payload.price else 18500.0

    # Calculate entry/stop/tp
    if side == "long":
        stop = price - 8
        tp1 = price + 10
        tp2 = price + 20
    else:
        stop = price + 8
        tp1 = price - 10
        tp2 = price - 20

    signal_obj = Signal(
        symbol=symbol,
        side=side,
        entry_price=price,
        stop_loss=stop,
        tp1=tp1,
        tp2=tp2,
        confluence_score=2,
        components={"webhook": True},
        trend_direction="bullish" if side == "long" else "bearish",
        source="webhook",
    )
    doc = signal_obj.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.signals.insert_one(doc)

    signal_engine_state["total_signals"] += 1
    signal_engine_state["last_signal_time"] = datetime.now(timezone.utc).isoformat()

    # Send to Discord in background
    doc.pop("_id", None)
    background_tasks.add_task(send_discord_signal, doc)

    return {"status": "received", "signal_id": signal_obj.id, "side": side}


# Get all signals
@api_router.get("/signals")
async def get_signals(limit: int = 50, status: Optional[str] = None):
    """Get signal history"""
    query = {}
    if status:
        query["status"] = status
    signals = await db.signals.find(query, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return signals


# Update signal outcome
@api_router.patch("/signals/{signal_id}")
async def update_signal(signal_id: str, status: str, pnl_points: Optional[float] = None):
    """Update signal status (hit_tp1, hit_tp2, stopped, expired)"""
    update_data = {"status": status}
    if pnl_points is not None:
        update_data["pnl_points"] = pnl_points
    if status == "stopped":
        update_data["outcome"] = "loss"
    elif status in ("hit_tp1", "hit_tp2"):
        update_data["outcome"] = "win"

    result = await db.signals.update_one({"id": signal_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"message": "Updated"}


# Signal Engine Stats
@api_router.get("/signals/stats")
async def get_signal_stats():
    """Get signal performance metrics"""
    all_signals = await db.signals.find({}, {"_id": 0}).to_list(1000)
    closed = [s for s in all_signals if s.get("outcome") in ("win", "loss")]
    wins = [s for s in closed if s.get("outcome") == "win"]
    losses = [s for s in closed if s.get("outcome") == "loss"]
    active = [s for s in all_signals if s.get("status") == "active"]

    total_pnl = sum(s.get("pnl_points", 0) for s in closed if s.get("pnl_points"))
    avg_rr = 0
    if losses:
        avg_win_pts = sum(s.get("pnl_points", 0) for s in wins) / len(wins) if wins else 0
        avg_loss_pts = abs(sum(s.get("pnl_points", 0) for s in losses) / len(losses)) if losses else 1
        avg_rr = round(avg_win_pts / avg_loss_pts, 2) if avg_loss_pts > 0 else 0

    # Signal frequency (signals per day over last 7 days)
    seven_days_ago = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    recent = [s for s in all_signals if s.get("created_at", "") >= seven_days_ago]
    freq = round(len(recent) / 7, 1) if recent else 0

    return {
        "total_signals": len(all_signals),
        "active_signals": len(active),
        "closed_signals": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else 0,
        "total_pnl_points": round(total_pnl, 1),
        "avg_rr": avg_rr,
        "signal_frequency_per_day": freq,
        "missed_signals": signal_engine_state["errors"],
    }


# Kill Switch
@api_router.post("/signals/kill-switch")
async def toggle_kill_switch(request: KillSwitchRequest):
    """Enable/disable the kill switch"""
    signal_engine_state["kill_switch"] = request.enabled
    action = "ENABLED" if request.enabled else "DISABLED"
    logger.warning(f"Kill switch {action}: {request.reason or 'No reason'}")

    # Log to db
    await db.system_logs.insert_one({
        "event": "kill_switch",
        "action": action,
        "reason": request.reason,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"kill_switch": request.enabled, "message": f"Kill switch {action}"}


@api_router.get("/signals/kill-switch")
async def get_kill_switch():
    """Get kill switch status"""
    return {"kill_switch": signal_engine_state["kill_switch"]}


# System Health
@api_router.get("/signals/health")
async def get_system_health():
    """Get system health metrics"""
    total = signal_engine_state["total_signals"]
    errors = signal_engine_state["errors"]
    error_rate = round(errors / total * 100, 1) if total > 0 else 0

    # Check auto kill-switch threshold (>5% error rate)
    auto_kill = error_rate > 5 and total > 10

    discord_configured = bool(DISCORD_WEBHOOK_URL) and DISCORD_WEBHOOK_URL != "REPLACE_WITH_YOUR_DISCORD_WEBHOOK_URL"

    return {
        "status": "degraded" if signal_engine_state["kill_switch"] else ("warning" if error_rate > 3 else "healthy"),
        "kill_switch": signal_engine_state["kill_switch"],
        "auto_kill_triggered": auto_kill,
        "uptime_since": signal_engine_state["started_at"],
        "total_signals_processed": total,
        "errors": errors,
        "error_rate_pct": error_rate,
        "last_signal_time": signal_engine_state["last_signal_time"],
        "discord_configured": discord_configured,
    }


# Test Signal Generator
@api_router.post("/signals/test")
async def generate_test_signal(background_tasks: BackgroundTasks):
    """Generate a test signal matching Scalp Punch logic (EMA21 cross + VWAP)"""
    if signal_engine_state["kill_switch"]:
        return {"status": "blocked", "reason": "Kill switch active"}

    side = _rng.choice(["long", "short"])
    live_snap = get_last_mnq()
    live_anchor = live_snap.get("price") or 0
    if not live_anchor:
        live_anchor = (await refresh_mnq()).get("price") or 29500
    base_price = live_anchor + _rng.uniform(-50, 50)
    entry = round(base_price, 2)

    # Scalp Punch: EMA21 as spine, VWAP as institutional level
    swing_range = _rng.uniform(8, 18)
    sl_buffer = 0.25

    if side == "long":
        stop = round(entry - swing_range - sl_buffer, 2)
        tp1 = round(entry + swing_range * 1.2, 2)
        tp2 = round(entry + swing_range * 2.0, 2)
    else:
        stop = round(entry + swing_range + sl_buffer, 2)
        tp1 = round(entry - swing_range * 1.2, 2)
        tp2 = round(entry - swing_range * 2.0, 2)

    # Scalp Punch confluence: EMA21 crossover + VWAP filter
    ema21_cross = _rng.choice([True, True, True, False])
    vwap_confirm = side == "long"  # Above VWAP for longs
    score = int(ema21_cross) + int(vwap_confirm)

    signal_obj = Signal(
        symbol="MNQ",
        side=side,
        entry_price=entry,
        stop_loss=stop,
        tp1=tp1,
        tp2=tp2,
        confluence_score=score,
        components={
            "ema21_cross": ema21_cross,
            "vwap_filter": vwap_confirm,
        },
        trend_direction="bullish" if side == "long" else "bearish",
        source="test",
    )
    doc = signal_obj.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.signals.insert_one(doc)

    signal_engine_state["total_signals"] += 1
    signal_engine_state["last_signal_time"] = datetime.now(timezone.utc).isoformat()

    background_tasks.add_task(send_discord_signal, doc)

    # Remove MongoDB _id before returning
    doc.pop("_id", None)
    return {"status": "generated", "signal": doc}


# Pine Script Reference
_PINE_SCRIPT_V3 = '''//@version=5
strategy("MNQ Scalp Stacks v3", overlay=true,
     initial_capital=10000, pyramiding=0,
     commission_type=strategy.commission.percent, commission_value=0.01)

// ==================== CORE INDICATORS ====================

// EMA 21 Spine — The backbone of structure
emaLen = input.int(21, "EMA 21 Spine Length")
ema21 = ta.ema(close, emaLen)

// VWAP — Institutional level
vwapVal = ta.vwap(hlc3)

// ==================== RESISTANCE ZONE: 27,972 ====================
resistanceLevel = input.float(27972, "Resistance Level", step=1)
resistanceBuffer = input.float(5, "Resistance Suppression Zone (pts)", step=1)
inResistanceZone = math.abs(close - resistanceLevel) <= resistanceBuffer

// ==================== SIGNAL LOGIC ====================

// BUY Punch: Price crosses above BOTH EMA 21 and VWAP
buyPunchRaw = ta.crossover(close, ema21) and close > vwapVal
// SELL Punch: Price crosses below BOTH EMA 21 and VWAP
sellPunchRaw = ta.crossunder(close, ema21) and close < vwapVal

// Wave Validation: Suppress longs in resistance zone
buyPunch = buyPunchRaw and not inResistanceZone
sellPunch = sellPunchRaw

// ==================== ENTRIES & EXITS ====================

// Dynamic SL/TP based on recent swing
atrLen = input.int(14, "ATR Length for SL/TP")
atrVal = ta.atr(atrLen)
slMultiplier = input.float(1.5, "SL ATR Multiplier", step=0.1)
tpMultiplier = input.float(2.5, "TP ATR Multiplier", step=0.1)

if buyPunch
    strategy.entry("BUY", strategy.long)
    strategy.exit("BUY-exit", from_entry="BUY",
         stop=close - atrVal * slMultiplier,
         limit=close + atrVal * tpMultiplier)

if sellPunch
    strategy.entry("SELL", strategy.short)
    strategy.exit("SELL-exit", from_entry="SELL",
         stop=close + atrVal * slMultiplier,
         limit=close - atrVal * tpMultiplier)

// ==================== PLOTTING ====================

// EMA 21 Spine (white, thick — the backbone)
plot(ema21, "EMA 21 Spine", color=color.white, linewidth=3)

// VWAP (blue — institutional)
plot(vwapVal, "VWAP", color=color.blue, linewidth=2)

// Resistance Zone (27,972)
resistHigh = plot(resistanceLevel + resistanceBuffer, "Resist High", color=color.new(color.red, 80))
resistLow = plot(resistanceLevel - resistanceBuffer, "Resist Low", color=color.new(color.red, 80))
fill(resistHigh, resistLow, color=inResistanceZone ? color.new(color.red, 80) : color.new(color.red, 93), title="27972 Zone")

// Punch arrows
plotshape(buyPunch, title="BUY Punch", style=shape.triangleup, location=location.belowbar, color=color.green, size=size.small, text="BUY")
plotshape(sellPunch, title="SELL Punch", style=shape.triangledown, location=location.abovebar, color=color.red, size=size.small, text="SELL")

// Resistance suppression marker
plotshape(buyPunchRaw and inResistanceZone, title="Suppressed Long", style=shape.xcross, location=location.belowbar, color=color.new(color.orange, 30), size=size.tiny, text="BLOCKED")

// Background flash on signal
bgcolor(buyPunch ? color.new(color.green, 93) : sellPunch ? color.new(color.red, 93) : na)

// Psychological levels
plot(math.round(close / 100) * 100, "Level 00", color=color.new(color.gray, 70), style=plot.style_cross)
plot(math.round(close / 100) * 100 + 50, "Level 50", color=color.new(color.gray, 80), style=plot.style_cross)

// ==================== ALERTS (JSON for /api/webhook/tradingview) ====================
alertcondition(buyPunch, title="BUY PUNCH", message='{"type":"buy","symbol":"MNQ","price":"{{close}}","time":"{{time}}"}')
alertcondition(sellPunch, title="SELL PUNCH", message='{"type":"sell","symbol":"MNQ","price":"{{close}}","time":"{{time}}"}')
alertcondition(inResistanceZone, title="27972 RESISTANCE", message='{"type":"resistance","symbol":"MNQ","price":"{{close}}","level":"27972"}')
'''


def _build_webhook_instructions(base_url: str) -> str:
    backend = base_url.rstrip('/')
    return f"""
## MNQ Scalp Stacks v3 — TradingView Setup

### Webhook URL:
{backend}/api/webhook/tradingview

### Setup Steps:
1. Open TradingView -> MNQ 1-min chart (MNQ ONLY)
2. Pine Editor -> Paste script -> "Add to Chart"
3. Right-click chart -> Add Alert
4. Condition: "MNQ Scalp Stacks v3" -> "BUY PUNCH" or "SELL PUNCH"
5. Enable "Webhook URL" and paste the URL above
6. JSON auto-formatted by alertcondition

### v3 Signal Logic:
- EMA 21 Spine (white line — structure backbone)
- Session VWAP (blue line — institutional level)
- BUY PUNCH: Cross above EMA 21 + above VWAP
- SELL PUNCH: Cross below EMA 21 + below VWAP
- 27,972 Resistance: Longs SUPPRESSED within 5 points
- ATR-based dynamic SL/TP
- Psychological levels (00/50) plotted

### Wave Validation:
- All numeric data validated before signal fires
- Resistance zone blocks fake breakout longs
- JSON format matches /api/webhook/tradingview endpoint
"""


@api_router.get("/signals/pinescript")
async def get_pine_script(request: Request):
    """Get the MNQ Scalp Stacks v3 Master Punch Pine Script."""
    # Derive the public base URL from the incoming request (works in any env)
    base = str(request.base_url)
    proto = request.headers.get("x-forwarded-proto")
    if proto == "https" and base.startswith("http://"):
        base = "https://" + base[len("http://"):]
    return {
        "pine_script": _PINE_SCRIPT_V3,
        "webhook_instructions": _build_webhook_instructions(base),
        "webhook_url": "/api/webhook/tradingview",
    }

# ============== Backtest Routes ==============

@api_router.get("/backtests")
async def get_backtests():
    """Get all backtest results"""
    results = await db.backtests.find({}, {"_id": 0}).sort("created_at", -1).to_list(20)
    return results

@api_router.post("/backtests")
async def create_backtest(bt: BacktestCreate):
    """Submit a backtest result"""
    win_rate = round(bt.winning_trades / bt.total_trades * 100, 1) if bt.total_trades > 0 else 0
    backtest = BacktestResult(
        **bt.model_dump(),
        win_rate=win_rate,
    )
    doc = backtest.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.backtests.insert_one(doc)
    doc.pop("_id", None)
    return doc

@api_router.delete("/backtests/{backtest_id}")
async def delete_backtest(backtest_id: str):
    """Delete a backtest result"""
    result = await db.backtests.delete_one({"id": backtest_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return {"message": "Deleted"}

@api_router.get("/public/backtests")
async def get_public_backtests():
    """Public endpoint: Get latest backtest results for performance page"""
    results = await db.backtests.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    return results

@api_router.post("/backtests/seed-demo")
async def seed_demo_backtest():
    """Seed a demo backtest for display"""
    existing = await db.backtests.count_documents({})
    if existing > 0:
        return {"message": "Backtest data already exists"}

    demo = BacktestResult(
        strategy_name="MNQ Scalp Stack v2",
        timeframe="1m",
        symbol="MNQ",
        period_start="2025-10-01",
        period_end="2026-01-15",
        total_trades=312,
        winning_trades=218,
        losing_trades=94,
        win_rate=69.9,
        profit_factor=2.14,
        net_profit=4280.00,
        max_drawdown=-620.00,
        max_drawdown_pct=6.2,
        sharpe_ratio=1.87,
        avg_trade=13.72,
        avg_win=28.50,
        avg_loss=-14.20,
        largest_win=142.00,
        largest_loss=-48.00,
        max_consecutive_wins=11,
        max_consecutive_losses=4,
        notes="3.5 months | MNQ 1m | Session VWAP + Structure | $10K initial capital",
        is_verified=True,
    )
    doc = demo.model_dump()
    doc["created_at"] = doc["created_at"].isoformat()
    await db.backtests.insert_one(doc)
    doc.pop("_id", None)
    return {"message": "Demo backtest seeded", "backtest": doc}

# Seed default data
@api_router.post("/seed")
async def seed_data():
    """Seed default watchlist and checklist items"""
    # Check if already seeded
    existing_watchlist = await db.watchlist.count_documents({})
    existing_checklist = await db.checklist.count_documents({})
    
    if existing_watchlist > 0 and existing_checklist > 0:
        return {"message": "Data already seeded"}
    
    # Default watchlist - stocks only, MNQ tracked separately
    default_watchlist = [
        {"symbol": "SOFI", "name": "SoFi Technologies", "category": "stock", "notes": "Fintech scaling fast"},
        {"symbol": "NIO", "name": "NIO Inc", "category": "stock", "notes": "EV rebound play"},
        {"symbol": "RKLB", "name": "Rocket Lab", "category": "stock", "notes": "Space/defense contracts"},
        {"symbol": "PLUG", "name": "Plug Power", "category": "stock", "notes": "Hydrogen - risky but explosive"},
        {"symbol": "SNAP", "name": "Snap Inc", "category": "stock", "notes": "Volatile, good swings"},
    ]
    
    # Default checklist
    default_checklist = [
        {"text": "Check pre-market futures direction", "category": "premarket", "order": 1},
        {"text": "Review overnight news/earnings", "category": "premarket", "order": 2},
        {"text": "Mark key support/resistance levels", "category": "premarket", "order": 3},
        {"text": "Set daily max loss limit ($40)", "category": "premarket", "order": 4},
        {"text": "Price above VWAP for longs", "category": "rules", "order": 5},
        {"text": "9 EMA crosses 21 EMA", "category": "rules", "order": 6},
        {"text": "RSI confirms (>50 long, <50 short)", "category": "rules", "order": 7},
        {"text": "Max 2-3 trades per session", "category": "rules", "order": 8},
        {"text": "Stop if 2 consecutive losses", "category": "rules", "order": 9},
        {"text": "Journal all trades with notes", "category": "postmarket", "order": 10},
        {"text": "Review wins and losses", "category": "postmarket", "order": 11},
    ]
    
    # Clear and seed
    await db.watchlist.delete_many({})
    await db.checklist.delete_many({})
    
    for item in default_watchlist:
        watchlist_item = WatchlistItem(**item)
        doc = watchlist_item.model_dump()
        doc['created_at'] = doc['created_at'].isoformat()
        await db.watchlist.insert_one(doc)
    
    for item in default_checklist:
        checklist_item = ChecklistItem(**item)
        await db.checklist.insert_one(checklist_item.model_dump())
    
    return {"message": "Data seeded successfully"}


# ============== Public Performance Dashboard ==============

@api_router.get("/public/performance")
async def get_public_performance():
    """Public-facing performance data for the signal system"""
    all_signals = await db.signals.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
    closed = [s for s in all_signals if s.get("outcome") in ("win", "loss")]
    wins = [s for s in closed if s.get("outcome") == "win"]
    losses = [s for s in closed if s.get("outcome") == "loss"]
    active = [s for s in all_signals if s.get("status") == "active"]

    total_pnl = sum(s.get("pnl_points", 0) for s in closed if s.get("pnl_points"))
    win_rate = round(len(wins) / len(closed) * 100, 1) if closed else 0

    avg_win_pts = round(sum(s.get("pnl_points", 0) for s in wins) / len(wins), 1) if wins else 0
    avg_loss_pts = round(abs(sum(s.get("pnl_points", 0) for s in losses) / len(losses)), 1) if losses else 0
    avg_rr = round(avg_win_pts / avg_loss_pts, 2) if avg_loss_pts > 0 else 0

    # Build P&L curve data
    pnl_curve = []
    running_pnl = 0
    for sig in sorted(closed, key=lambda x: x.get("created_at", "")):
        running_pnl += sig.get("pnl_points", 0)
        pnl_curve.append({
            "date": sig.get("created_at", "")[:10],
            "pnl": round(running_pnl, 1),
            "side": sig.get("side", ""),
            "outcome": sig.get("outcome", ""),
        })

    # Recent signals (public view - limited info)
    recent_public = []
    for sig in all_signals[:15]:
        recent_public.append({
            "id": sig["id"],
            "symbol": sig.get("symbol", "MNQ"),
            "side": sig.get("side", ""),
            "entry_price": sig.get("entry_price", 0),
            "tp1": sig.get("tp1", 0),
            "tp2": sig.get("tp2", 0),
            "stop_loss": sig.get("stop_loss", 0),
            "confluence_score": sig.get("confluence_score", 0),
            "status": sig.get("status", ""),
            "outcome": sig.get("outcome"),
            "pnl_points": sig.get("pnl_points"),
            "created_at": sig.get("created_at", ""),
        })

    # Best streak calculation
    current_streak = 0
    best_streak = 0
    for sig in sorted(closed, key=lambda x: x.get("created_at", "")):
        if sig.get("outcome") == "win":
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            current_streak = 0

    return {
        "overview": {
            "total_signals": len(all_signals),
            "closed_signals": len(closed),
            "active_signals": len(active),
            "win_rate": win_rate,
            "total_pnl_points": round(total_pnl, 1),
            "avg_win_points": avg_win_pts,
            "avg_loss_points": avg_loss_pts,
            "avg_rr": avg_rr,
            "best_win_streak": best_streak,
            "wins": len(wins),
            "losses": len(losses),
        },
        "pnl_curve": pnl_curve,
        "recent_signals": recent_public,
    }


@api_router.post("/public/seed-demo")
async def seed_demo_performance():
    """Seed demo performance data for the public dashboard"""

    existing = await db.signals.count_documents({"source": "demo"})
    if existing > 0:
        return {"message": "Demo data already seeded"}

    # Generate 30 days of realistic signal history
    outcomes = (
        [("win", 10, "hit_tp1")] * 6 +
        [("win", 20, "hit_tp2")] * 3 +
        [("loss", -8, "stopped")] * 4
    )  # ~69% win rate, positive expectancy

    base_time = datetime.now(timezone.utc) - timedelta(days=30)
    signals_to_insert = []

    for day_offset in range(30):
        day = base_time + timedelta(days=day_offset)
        # 1-3 signals per day
        num_signals = _rng.randint(1, 3)
        for i in range(num_signals):
            outcome_data = _rng.choice(outcomes)
            outcome, pnl, status = outcome_data
            side = _rng.choice(["long", "short"])
            base_price = 18300 + _rng.uniform(-200, 200)
            entry = round(base_price, 2)

            if side == "long":
                stop = round(entry - 8, 2)
                tp1 = round(entry + 10, 2)
                tp2 = round(entry + 20, 2)
            else:
                stop = round(entry + 8, 2)
                tp1 = round(entry - 10, 2)
                tp2 = round(entry - 20, 2)

            score = _rng.randint(2, 3)
            sig_time = day + timedelta(hours=_rng.choice([9, 10, 15, 16]), minutes=_rng.randint(0, 59))

            sig = {
                "id": str(uuid.uuid4()),
                "symbol": "MNQ",
                "side": side,
                "entry_price": entry,
                "stop_loss": stop,
                "tp1": tp1,
                "tp2": tp2,
                "confluence_score": score,
                "components": {
                    "near_level": _rng.choice([True, False]),
                    "rejection": True,
                    "momentum_break": score >= 2,
                },
                "trend_direction": "bullish" if side == "long" else "bearish",
                "status": status,
                "outcome": outcome,
                "pnl_points": pnl,
                "discord_sent": True,
                "source": "demo",
                "created_at": sig_time.isoformat(),
            }
            signals_to_insert.append(sig)

    if signals_to_insert:
        await db.signals.insert_many(signals_to_insert)

    return {"message": f"Seeded {len(signals_to_insert)} demo signals"}


# ============== Subscriber & Stripe Routes ==============

from emergentintegrations.payments.stripe.checkout import StripeCheckout, CheckoutSessionRequest

@api_router.post("/subscribers")
async def create_subscriber(sub: SubscriberCreate):
    """Register a new subscriber with referral + welcome sequence"""
    # Check if email already exists
    existing = await db.subscribers.find_one({"email": sub.email}, {"_id": 0})
    if existing:
        return {
            "status": "existing",
            "subscriber": existing,
            "discord_invite": DISCORD_INVITES.get(existing.get("tier", "free"), ""),
        }

    # Generate unique referral code
    ref_code = hashlib.sha256(sub.email.encode()).hexdigest()[:8].upper()

    subscriber = {
        "id": str(uuid.uuid4()),
        "email": sub.email,
        "name": sub.name or "",
        "tier": sub.tier,
        "status": "active",
        "stripe_session_id": None,
        "referral_code": ref_code,
        "referred_by": None,
        "referral_count": 0,
        "referral_credits": 0,
        "welcome_step": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Process referral if code provided
    if sub.referral_code:
        referrer = await db.subscribers.find_one({"referral_code": sub.referral_code}, {"_id": 0})
        if referrer:
            subscriber["referred_by"] = referrer["id"]
            # Credit the referrer
            await db.subscribers.update_one(
                {"id": referrer["id"]},
                {"$inc": {"referral_count": 1, "referral_credits": 1}}
            )

    await db.subscribers.insert_one(subscriber)
    subscriber.pop("_id", None)

    # Create welcome sequence
    welcome_steps = [
        {"step": 1, "title": "Welcome to MNQ SCALP STACKS", "message": f"Hey {sub.name or 'Trader'}! Your account is active. Here's what's next.", "type": "welcome", "delay_hours": 0},
        {"step": 2, "title": "Join the Discord", "message": "Connect with other traders in our Discord community. Signals are delivered here in real-time.", "type": "action", "delay_hours": 0},
        {"step": 3, "title": "Set Up TradingView", "message": "Load the MNQ Scalp Stack v2 Pine Script on your chart. Check the dashboard for the full script.", "type": "setup", "delay_hours": 1},
        {"step": 4, "title": "Your First Signal", "message": "Signals fire when VWAP + RSI + Structure align. Watch for your first alert!", "type": "education", "delay_hours": 24},
        {"step": 5, "title": "Share & Earn", "message": f"Your referral code: {ref_code}. Each friend you bring = 1 month free credit!", "type": "referral", "delay_hours": 72},
    ]

    for ws in welcome_steps:
        await db.welcome_sequence.insert_one({
            "id": str(uuid.uuid4()),
            "subscriber_id": subscriber["id"],
            "email": sub.email,
            **ws,
            "completed": ws["delay_hours"] == 0,
            "sent_at": datetime.now(timezone.utc).isoformat() if ws["delay_hours"] == 0 else None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "status": "created",
        "subscriber": subscriber,
        "discord_invite": DISCORD_INVITES.get(sub.tier, ""),
        "referral_code": ref_code,
    }


@api_router.get("/subscribers/count")
async def get_subscriber_count():
    """Get total subscriber count (public metric)"""
    total = await db.subscribers.count_documents({})
    pro = await db.subscribers.count_documents({"tier": "pro"})
    elite = await db.subscribers.count_documents({"tier": "elite"})
    return {"total": total, "free": total - pro - elite, "pro": pro, "elite": elite}


@api_router.get("/referral/{code}")
async def get_referral_info(code: str):
    """Get referral info by code"""
    referrer = await db.subscribers.find_one({"referral_code": code}, {"_id": 0})
    if not referrer:
        raise HTTPException(status_code=404, detail="Referral code not found")
    return {
        "valid": True,
        "referrer_name": referrer.get("name", "A trader"),
        "code": code,
    }


@api_router.get("/referral/stats/{subscriber_id}")
async def get_referral_stats(subscriber_id: str):
    """Get referral stats for a subscriber"""
    sub = await db.subscribers.find_one({"id": subscriber_id}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    referrals = await db.subscribers.find({"referred_by": subscriber_id}, {"_id": 0}).to_list(100)
    return {
        "referral_code": sub.get("referral_code", ""),
        "referral_count": sub.get("referral_count", 0),
        "referral_credits": sub.get("referral_credits", 0),
        "referrals": [{"name": r.get("name", ""), "email": r.get("email", "")[:3] + "***", "tier": r.get("tier"), "date": r.get("created_at")} for r in referrals],
    }


@api_router.get("/welcome/{subscriber_id}")
async def get_welcome_sequence(subscriber_id: str):
    """Get welcome sequence steps for a subscriber"""
    steps = await db.welcome_sequence.find({"subscriber_id": subscriber_id}, {"_id": 0}).sort("step", 1).to_list(10)
    return steps


@api_router.patch("/welcome/{step_id}/complete")
async def complete_welcome_step(step_id: str):
    """Mark a welcome step as completed"""
    result = await db.welcome_sequence.update_one(
        {"id": step_id},
        {"$set": {"completed": True, "sent_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Step not found")
    return {"message": "Completed"}


@api_router.get("/subscribers/tiers")
async def get_tiers():
    """Get available subscription tiers"""
    tiers = []
    for key, tier in SUBSCRIPTION_TIERS.items():
        tiers.append({
            "id": key,
            "name": tier["name"],
            "price": tier["price"],
            "features": {
                "free": ["Basic signals (delayed)", "Public performance dashboard", "Discord community access"],
                "pro": ["Real-time signals", "Discord Pro channel", "AI trade analysis", "Daily market briefing"],
                "elite": ["Everything in Pro", "Discord Elite channel", "1-on-1 trade review", "Priority signal delivery", "Custom alert setup"],
            }.get(key, []),
        })
    return tiers


@api_router.post("/checkout/create")
async def create_checkout(request: CheckoutRequest, http_request: Request):
    """Create Stripe checkout session for paid tiers"""
    tier = request.tier
    if tier not in ("pro", "elite"):
        raise HTTPException(status_code=400, detail="Invalid tier. Choose 'pro' or 'elite'")

    amount = SUBSCRIPTION_TIERS[tier]["price"]
    origin = request.origin_url.rstrip("/")
    success_url = f"{origin}/performance?session_id={{CHECKOUT_SESSION_ID}}&tier={tier}"
    cancel_url = f"{origin}/performance"

    host_url = str(http_request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"

    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    checkout_req = CheckoutSessionRequest(
        amount=amount,
        currency="usd",
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"tier": tier, "product": f"MNQ Stack Signals - {tier.title()}", "email": request.email.lower()},
    )

    session = await stripe_checkout.create_checkout_session(checkout_req)

    # Create payment transaction record
    await db.payment_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session.session_id,
        "tier": tier,
        "amount": amount,
        "currency": "usd",
        "payment_status": "pending",
        "metadata": {"tier": tier},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    return {"url": session.url, "session_id": session.session_id}


@api_router.get("/checkout/status/{session_id}")
async def get_checkout_status(session_id: str, http_request: Request):
    """Check payment status and activate subscription"""
    host_url = str(http_request.base_url)
    webhook_url = f"{host_url}api/webhook/stripe"
    stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)

    status = await stripe_checkout.get_checkout_status(session_id)

    # Update payment transaction
    tx = await db.payment_transactions.find_one({"session_id": session_id}, {"_id": 0})
    if tx and tx.get("payment_status") != "paid":
        await db.payment_transactions.update_one(
            {"session_id": session_id},
            {"$set": {
                "payment_status": status.payment_status,
                "status": status.status,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )

    meta = status.metadata or {}
    if status.payment_status == "paid" and meta.get("email"):
        tier = meta.get("tier", "pro")
        await db.users.update_one({"email": meta["email"]}, {"$set": {"tier": tier}})
        await db.subscribers.update_one(
            {"email": meta["email"]},
            {"$set": {"tier": tier, "stripe_session_id": session_id}},
        )
    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "metadata": status.metadata,
        "discord_invite": DISCORD_INVITES.get((status.metadata or {}).get("tier", ""), ""),
    }


@api_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    body = await request.body()
    signature = request.headers.get("Stripe-Signature", "")

    try:
        host_url = str(request.base_url)
        webhook_url = f"{host_url}api/webhook/stripe"
        stripe_checkout = StripeCheckout(api_key=STRIPE_API_KEY, webhook_url=webhook_url)
        event = await stripe_checkout.handle_webhook(body, signature)

        if event.payment_status == "paid":
            # Update transaction
            await db.payment_transactions.update_one(
                {"session_id": event.session_id},
                {"$set": {
                    "payment_status": "paid",
                    "event_type": event.event_type,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            # Upgrade subscriber if metadata has tier
            tier = event.metadata.get("tier", "pro") if event.metadata else "pro"
            email = event.metadata.get("email", "") if event.metadata else ""
            if email:
                await db.subscribers.update_one(
                    {"email": email},
                    {"$set": {"tier": tier, "stripe_session_id": event.session_id}}
                )
                # Auto-upgrade the logged-in user's account tier
                await db.users.update_one({"email": email}, {"$set": {"tier": tier}})

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return {"status": "error", "detail": str(e)}


# ============== Auto-Trade Logging ==============

@api_router.post("/signals/{signal_id}/auto-log")
async def auto_log_trade(signal_id: str, outcome: str, pnl_points: Optional[float] = None):
    """Auto-log a trade from signal outcome (TP1/TP2/Stopped)"""
    signal = await db.signals.find_one({"id": signal_id}, {"_id": 0})
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")

    # Update signal status
    update_data = {"status": outcome}
    if outcome in ("hit_tp1", "hit_tp2"):
        update_data["outcome"] = "win"
        if outcome == "hit_tp1":
            pnl_points = pnl_points or abs(signal["tp1"] - signal["entry_price"])
        else:
            pnl_points = pnl_points or abs(signal["tp2"] - signal["entry_price"])
    elif outcome == "stopped":
        update_data["outcome"] = "loss"
        pnl_points = pnl_points or -abs(signal["stop_loss"] - signal["entry_price"])

    update_data["pnl_points"] = round(pnl_points, 2) if pnl_points else 0
    await db.signals.update_one({"id": signal_id}, {"$set": update_data})

    # Auto-create trade journal entry
    entry_price = signal["entry_price"]
    if outcome == "hit_tp1":
        exit_price = signal["tp1"]
    elif outcome == "hit_tp2":
        exit_price = signal["tp2"]
    else:
        exit_price = signal["stop_loss"]

    side = signal.get("side", "long")
    if side == "long":
        pnl_dollar = (exit_price - entry_price) * 2  # MNQ = $2/point
    else:
        pnl_dollar = (entry_price - exit_price) * 2

    trade_doc = {
        "id": str(uuid.uuid4()),
        "symbol": signal.get("symbol", "MNQ"),
        "entry_price": entry_price,
        "exit_price": exit_price,
        "quantity": 1,
        "side": side,
        "status": "closed",
        "entry_date": signal.get("created_at", datetime.now(timezone.utc).isoformat()),
        "exit_date": datetime.now(timezone.utc).isoformat(),
        "pnl": round(pnl_dollar, 2),
        "notes": f"Auto-logged from signal {signal_id[:8]} | {outcome}",
    }
    await db.trades.insert_one(trade_doc)
    trade_doc.pop("_id", None)

    return {"status": "logged", "signal_outcome": outcome, "trade": trade_doc}


# ============== Admin Panel Routes ==============

@api_router.get("/admin/overview")
async def admin_overview():
    """Admin dashboard overview"""
    total_subs = await db.subscribers.count_documents({})
    pro_subs = await db.subscribers.count_documents({"tier": "pro"})
    elite_subs = await db.subscribers.count_documents({"tier": "elite"})
    total_signals = await db.signals.count_documents({})
    active_signals = await db.signals.count_documents({"status": "active"})
    total_trades = await db.trades.count_documents({})
    total_payments = await db.payment_transactions.count_documents({"payment_status": "paid"})

    # Revenue calculation
    revenue = (pro_subs * 49) + (elite_subs * 149)

    # Recent activity
    recent_subs = await db.subscribers.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)
    recent_signals = await db.signals.find({}, {"_id": 0}).sort("created_at", -1).to_list(5)

    return {
        "subscribers": {"total": total_subs, "free": total_subs - pro_subs - elite_subs, "pro": pro_subs, "elite": elite_subs},
        "signals": {"total": total_signals, "active": active_signals},
        "trades": {"total": total_trades},
        "revenue": {"mrr": revenue, "total_payments": total_payments},
        "recent_subscribers": recent_subs,
        "recent_signals": recent_signals,
    }


@api_router.get("/admin/subscribers")
async def admin_get_subscribers(limit: int = 50):
    """Get all subscribers for admin"""
    subs = await db.subscribers.find({}, {"_id": 0}).sort("created_at", -1).to_list(limit)
    return subs


@api_router.patch("/admin/subscribers/{sub_id}/tier")
async def admin_update_tier(sub_id: str, tier: str):
    """Admin: update subscriber tier"""
    if tier not in ("free", "pro", "elite"):
        raise HTTPException(status_code=400, detail="Invalid tier")
    result = await db.subscribers.update_one({"id": sub_id}, {"$set": {"tier": tier}})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"message": f"Tier updated to {tier}"}


@api_router.delete("/admin/subscribers/{sub_id}")
async def admin_delete_subscriber(sub_id: str):
    """Admin: remove subscriber"""
    result = await db.subscribers.delete_one({"id": sub_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subscriber not found")
    return {"message": "Deleted"}


# ============== Public Leaderboard ==============

@api_router.get("/public/leaderboard")
async def get_leaderboard():
    """Public leaderboard: top referrers + top signals"""
    # Top referrers
    all_subs = await db.subscribers.find({"referral_count": {"$gt": 0}}, {"_id": 0}).sort("referral_count", -1).to_list(10)
    top_referrers = [
        {"name": s.get("name") or s.get("email", "")[:3] + "***", "referrals": s.get("referral_count", 0), "tier": s.get("tier", "free")}
        for s in all_subs
    ]

    # Top signal streaks (best consecutive wins)
    closed_signals = await db.signals.find({"outcome": {"$in": ["win", "loss"]}}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    current_streak = 0
    best_streak = 0
    streak_history = []
    for sig in closed_signals:
        if sig.get("outcome") == "win":
            current_streak += 1
            best_streak = max(best_streak, current_streak)
        else:
            if current_streak >= 3:
                streak_history.append(current_streak)
            current_streak = 0

    # Monthly stats
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_signals = await db.signals.find({"created_at": {"$gte": month_start}, "outcome": {"$in": ["win", "loss"]}}, {"_id": 0}).to_list(500)
    month_wins = len([s for s in month_signals if s.get("outcome") == "win"])
    month_total = len(month_signals)
    month_pnl = sum(s.get("pnl_points", 0) for s in month_signals)

    return {
        "top_referrers": top_referrers,
        "best_win_streak": best_streak,
        "month_stats": {
            "signals": month_total,
            "wins": month_wins,
            "win_rate": round(month_wins / month_total * 100, 1) if month_total > 0 else 0,
            "pnl_points": round(month_pnl, 1),
        },
        "total_subscribers": await db.subscribers.count_documents({}),
    }


# ============== OPERATOR COCKPIT (Personal Trading Engine) ==============

# In-memory operator state (single-operator personal cockpit)
_operator_state = {
    "connection": {"broker": "NinjaTrader", "status": "DISCONNECTED", "account": "Sim101"},
    "balance": 100000.00,
    "daily_pnl": 0.0,
    "daily_trades": 0,
    "max_daily_loss": -1000.00,
    "max_daily_trades": 20,
    "session_started_at": datetime.now(timezone.utc).isoformat(),
    "automation_paused": False,
    "kill_switch": False,
    "last_order_at": 0.0,  # unix ts
    "position": {"side": None, "qty": 0, "avg_entry": 0.0, "unrealized_pnl": 0.0},
}

# Order cooldown (server-side, ms)
_ORDER_COOLDOWN_MS = 1500


class OperatorOrder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    action: str  # BUY | SELL | CLOSE_LONG | CLOSE_SHORT | BREAK_EVEN
    symbol: str = "MNQ"
    qty: int = 1
    order_type: str = "MARKET"  # MARKET | LIMIT
    limit_price: Optional[float] = None
    sl_ticks: Optional[int] = None  # Stop-loss distance in ticks (attached bracket)
    tp_ticks: Optional[int] = None  # Take-profit distance in ticks (attached bracket)
    preset: Optional[str] = None    # Human label e.g. "SNIPE_2R"


def _ny_session_open() -> bool:
    """Rough NY equity-session check (Mon–Fri 09:30–16:00 ET, naive UTC offset)."""
    now = datetime.now(timezone.utc)
    if now.weekday() >= 5:
        return False
    ny_minutes = (now.hour - 5) % 24 * 60 + now.minute
    return 9 * 60 + 30 <= ny_minutes <= 16 * 60


@api_router.get("/operator/state", tags=["operator"])
async def operator_state() -> Dict[str, Any]:
    s = dict(_operator_state)
    # Live connection status derives from the ATI bridge heartbeat
    s["connection"] = {
        **s["connection"],
        "status": "CONNECTED" if (ati.ati_enabled() and ati.bridge_online()) else "DISCONNECTED",
        "ati_enabled": ati.ati_enabled(),
        "bridge_online": ati.bridge_online(),
    }
    s["session_seconds"] = int(
        (datetime.now(timezone.utc) - datetime.fromisoformat(s["session_started_at"])).total_seconds()
    )
    s["market_open"] = _ny_session_open()
    s["cooldown_ms_remaining"] = max(
        0, int(_ORDER_COOLDOWN_MS - (datetime.now(timezone.utc).timestamp() - s["last_order_at"]) * 1000)
    )
    return s


_EMPTY_CANDLE_RESPONSE: Dict[str, Any] = {
    "symbol": "MNQ", "candles": [], "ema9": [], "ema21": [], "vwap": [],
    "last_close": None, "source": "empty",
}


def _aggregate_bars(bars: List[Dict[str, Any]], tf_seconds: int, count: int) -> List[Dict[str, Any]]:
    """Roll up 1-minute bars to the requested timeframe."""
    if tf_seconds == 60:
        return bars[-count:]
    bucket: Dict[int, Dict[str, Any]] = {}
    for b in bars:
        slot = (b["time"] // tf_seconds) * tf_seconds
        cur = bucket.get(slot)
        if cur is None:
            bucket[slot] = {"time": slot, "open": b["open"], "high": b["high"],
                            "low": b["low"], "close": b["close"], "volume": b["volume"]}
        else:
            cur["high"] = max(cur["high"], b["high"])
            cur["low"] = min(cur["low"], b["low"])
            cur["close"] = b["close"]
            cur["volume"] += b["volume"]
    return list(bucket.values())[-count:]


def _series_ema(closes: List[float], period: int) -> List[Optional[float]]:
    """Standard EMA series with None padding for the first (period-1) values."""
    if len(closes) < period:
        return []
    k = 2 / (period + 1)
    out: List[Optional[float]] = [None] * (period - 1)
    seed = sum(closes[:period]) / period
    out.append(round(seed, 2))
    for i in range(period, len(closes)):
        seed = closes[i] * k + seed * (1 - k)
        out.append(round(seed, 2))
    return out


def _series_vwap(agg: List[Dict[str, Any]]) -> List[Optional[float]]:
    cum_pv, cum_v, line = 0.0, 0.0, []
    for k in agg:
        typ = (k["high"] + k["low"] + k["close"]) / 3
        vol = k["volume"] or 1
        cum_pv += typ * vol
        cum_v += vol
        line.append(round(cum_pv / cum_v, 2) if cum_v else None)
    return line


def _line_points(agg: List[Dict[str, Any]], series: List[Optional[float]]) -> List[Dict[str, Any]]:
    return [{"time": c["time"], "value": v} for c, v in zip(agg, series) if v is not None]


@api_router.get("/operator/candles", tags=["operator"])
async def operator_candles(timeframe: str = "1m", count: int = 120) -> Dict[str, Any]:
    """Real intraday candles from the live MNQ feed (Yahoo NQ=F)."""
    from market_feed import get_bars
    bars = get_bars()
    if not bars:
        await refresh_mnq()
        bars = get_bars()
    if not bars:
        return {**_EMPTY_CANDLE_RESPONSE, "timeframe": timeframe}

    tf_seconds = {"1m": 60, "5m": 300, "15m": 900}.get(timeframe, 60)
    agg = _aggregate_bars(bars, tf_seconds, count)
    closes = [k["close"] for k in agg]

    return {
        "symbol": "MNQ",
        "timeframe": timeframe,
        "candles": agg,
        "ema9": _line_points(agg, _series_ema(closes, 9)),
        "ema21": _line_points(agg, _series_ema(closes, 21)),
        "vwap": _line_points(agg, _series_vwap(agg)),
        "last_close": agg[-1]["close"] if agg else None,
        "source": "yahoo:NQ=F",
    }


# Synthetic candle generator was removed (2026-02-22) — live Yahoo feed is the only source.


def _validate_order(order: OperatorOrder, now_ts: float) -> None:
    """Run safety chain on every order. Raises HTTPException on first violation."""
    if _operator_state["kill_switch"]:
        raise HTTPException(status_code=423, detail="KILL_SWITCH active — orders blocked")
    if _operator_state["automation_paused"] and order.action.startswith(("AUTO_",)):
        raise HTTPException(status_code=423, detail="Automation paused")
    if _operator_state["daily_pnl"] <= _operator_state["max_daily_loss"]:
        raise HTTPException(status_code=423, detail="Max daily loss hit — locked out")
    if _operator_state["daily_trades"] >= _operator_state["max_daily_trades"]:
        raise HTTPException(status_code=423, detail="Max daily trades reached")
    elapsed_ms = (now_ts - _operator_state["last_order_at"]) * 1000
    if elapsed_ms < _ORDER_COOLDOWN_MS:
        raise HTTPException(status_code=429, detail=f"Cooldown — wait {int(_ORDER_COOLDOWN_MS - elapsed_ms)}ms")
    if order.order_type == "LIMIT" and order.limit_price is None:
        raise HTTPException(status_code=400, detail="LIMIT order requires limit_price")


async def _resolve_fill_price(order: OperatorOrder) -> float:
    """LIMIT → user price. MARKET → live feed cache (or refresh once if cold)."""
    if order.order_type == "LIMIT" and order.limit_price:
        return order.limit_price
    live_price = get_last_mnq().get("price") or 0.0
    if not live_price:
        live_price = (await refresh_mnq()).get("price") or 0.0
    if not live_price:
        raise HTTPException(status_code=503, detail="No live MNQ price available — feed offline")
    return live_price


def _weighted_avg(prev_qty: int, prev_avg: float, add_qty: int, add_price: float) -> float:
    """Compute new average entry when stacking onto an existing position."""
    new_qty = prev_qty + add_qty
    if not new_qty:
        return add_price
    return ((prev_avg * prev_qty) + (add_price * add_qty)) / new_qty


def _flat_position() -> Dict[str, Any]:
    return {"side": None, "qty": 0, "avg_entry": 0.0, "unrealized_pnl": 0.0}


def _apply_fill(order: OperatorOrder, fill_price: float) -> None:
    """Mutate _operator_state['position'] and ['daily_pnl'] based on the action."""
    pos = _operator_state["position"]
    action = order.action

    if action == "BUY":
        if pos["side"] == "SHORT":
            pnl = (pos["avg_entry"] - fill_price) * pos["qty"] * 2
            _operator_state["daily_pnl"] += pnl
            _operator_state["position"] = _flat_position()
        else:
            new_qty = pos["qty"] + order.qty
            new_avg = _weighted_avg(pos["qty"], pos["avg_entry"], order.qty, fill_price)
            _operator_state["position"] = {"side": "LONG", "qty": new_qty, "avg_entry": round(new_avg, 2), "unrealized_pnl": 0.0}
    elif action == "SELL":
        if pos["side"] == "LONG":
            pnl = (fill_price - pos["avg_entry"]) * pos["qty"] * 2
            _operator_state["daily_pnl"] += pnl
            _operator_state["position"] = _flat_position()
        else:
            new_qty = pos["qty"] + order.qty
            new_avg = _weighted_avg(pos["qty"], pos["avg_entry"], order.qty, fill_price)
            _operator_state["position"] = {"side": "SHORT", "qty": new_qty, "avg_entry": round(new_avg, 2), "unrealized_pnl": 0.0}
    elif action in ("CLOSE_LONG", "CLOSE_SHORT") and pos["side"]:
        mult = 1 if pos["side"] == "LONG" else -1
        pnl = (fill_price - pos["avg_entry"]) * pos["qty"] * 2 * mult
        _operator_state["daily_pnl"] += pnl
        _operator_state["position"] = _flat_position()
    # BREAK_EVEN is a no-op on PnL (SL→BE marker only in a real engine)

    _operator_state["daily_pnl"] = round(_operator_state["daily_pnl"], 2)


def _bracket_price(action: str, fill_price: float, ticks: Optional[int], is_stop: bool) -> Optional[float]:
    """Compute SL or TP price from ticks distance. SL goes against, TP with."""
    if ticks is None:
        return None
    ticks_pts = ticks * 0.25
    if action == "BUY":
        return round(fill_price - ticks_pts if is_stop else fill_price + ticks_pts, 2)
    if action == "SELL":
        return round(fill_price + ticks_pts if is_stop else fill_price - ticks_pts, 2)
    return None


def _build_journal_entry(order: OperatorOrder, fill_price: float) -> Dict[str, Any]:
    return {
        "id": str(uuid.uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "action": order.action,
        "symbol": order.symbol,
        "qty": order.qty,
        "order_type": order.order_type,
        "limit_price": order.limit_price,
        "fill_price": fill_price,
        "sl_ticks": order.sl_ticks,
        "tp_ticks": order.tp_ticks,
        "preset": order.preset,
        "sl_price": _bracket_price(order.action, fill_price, order.sl_ticks, is_stop=True),
        "tp_price": _bracket_price(order.action, fill_price, order.tp_ticks, is_stop=False),
        "resulting_position": _operator_state["position"],
        "daily_pnl": _operator_state["daily_pnl"],
        "phase": "SIM_LOG_ONLY",
    }


@api_router.post("/operator/order", tags=["operator"], dependencies=[Depends(require_write_key)])
async def operator_order(order: OperatorOrder) -> Dict[str, Any]:
    """Server-side validated order. PHASE 1: logs only, does NOT submit to a broker."""
    now_ts = datetime.now(timezone.utc).timestamp()
    _validate_order(order, now_ts)

    _operator_state["last_order_at"] = now_ts
    _operator_state["daily_trades"] += 1

    fill_price = await _resolve_fill_price(order)
    _apply_fill(order, fill_price)

    entry = _build_journal_entry(order, fill_price)
    ati_cmd = None
    try:
        await db.operator_orders.insert_one(dict(entry))
    except Exception as e:
        logger.warning(f"operator_orders insert failed: {e}")
    try:
        ati_cmd = await ati.enqueue(db, ati.build_ati_command_for_order(order, entry["id"]))
    except Exception as e:
        logger.warning(f"ati enqueue failed: {e}")

    return {
        "ok": True,
        "order": entry,
        "state": _operator_state["position"],
        "ati": {"routed": ati_cmd is not None, "command_id": ati_cmd["id"] if ati_cmd else None},
    }


@api_router.post("/operator/control/{action}", tags=["operator"], dependencies=[Depends(require_write_key)])
async def operator_control(action: str) -> Dict[str, Any]:
    """Master controls: flatten | pause | resume | kill | reset_session"""
    action = action.lower()
    if action == "flatten":
        _operator_state["position"] = {"side": None, "qty": 0, "avg_entry": 0.0, "unrealized_pnl": 0.0}
        await db.operator_orders.insert_one({
            "id": str(uuid.uuid4()), "ts": datetime.now(timezone.utc).isoformat(),
            "action": "FLATTEN_ALL", "phase": "SIM_LOG_ONLY",
        })
        await ati.enqueue(db, ati.build_flatten_command())
        return {"ok": True, "action": "FLATTEN", "position": _operator_state["position"]}
    if action == "pause":
        _operator_state["automation_paused"] = True
        return {"ok": True, "automation_paused": True}
    if action == "resume":
        _operator_state["automation_paused"] = False
        return {"ok": True, "automation_paused": False}
    if action == "kill":
        _operator_state["kill_switch"] = True
        _operator_state["position"] = {"side": None, "qty": 0, "avg_entry": 0.0, "unrealized_pnl": 0.0}
        await ati.enqueue(db, ati.build_flatten_command())
        return {"ok": True, "kill_switch": True}
    if action == "unkill":
        _operator_state["kill_switch"] = False
        return {"ok": True, "kill_switch": False}
    if action == "reset_session":
        _operator_state["daily_pnl"] = 0.0
        _operator_state["daily_trades"] = 0
        _operator_state["session_started_at"] = datetime.now(timezone.utc).isoformat()
        _operator_state["position"] = {"side": None, "qty": 0, "avg_entry": 0.0, "unrealized_pnl": 0.0}
        return {"ok": True, "action": "RESET_SESSION"}
    raise HTTPException(status_code=400, detail=f"Unknown control action: {action}")


@api_router.get("/operator/journal", tags=["operator"])
async def operator_journal(
    limit: int = 20,
    skip: int = 0,
    action: Optional[str] = None,
    since: Optional[str] = None,  # ISO timestamp
) -> Dict[str, Any]:
    """Paginated operator order journal. Retool-friendly."""
    query: Dict[str, Any] = {}
    if action:
        query["action"] = action.upper()
    if since:
        query["ts"] = {"$gte": since}
    total = await db.operator_orders.count_documents(query)
    rows = (
        await db.operator_orders
        .find(query, {"_id": 0})
        .sort("ts", -1)
        .skip(skip)
        .limit(limit)
        .to_list(length=limit)
    )
    return {"entries": rows, "total": total, "limit": limit, "skip": skip}


# ============== AFFILIATE CLICK TRACKING (Revenue) ==============

@api_router.get("/r/{partner}")
async def affiliate_redirect(partner: str, request: Request, src: Optional[str] = None):
    """Logs an outbound affiliate click then 302-redirects to the partner URL.

    URL format: /api/r/{partner}?src={cta_id}
    partner: ninjatrader | tradingview | gpay | discord
    """
    partner_key = partner.lower().strip()
    target = AFFILIATE_URLS.get(partner_key)
    if not target:
        raise HTTPException(status_code=404, detail=f"Unknown partner: {partner}")

    try:
        await db.affiliate_clicks.insert_one({
            "id": str(uuid.uuid4()),
            "partner": partner_key,
            "src": (src or "unknown")[:64],
            "referrer": (request.headers.get("referer") or "")[:256],
            "ua": (request.headers.get("user-agent") or "")[:256],
            "ip_hash": hashlib.sha256(
                (request.client.host if request.client else "0.0.0.0").encode()
            ).hexdigest()[:16],
            "ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"affiliate_clicks insert failed: {e}")

    return RedirectResponse(url=target, status_code=302)


@api_router.get("/admin/clicks", tags=["admin"])
async def affiliate_click_stats() -> Dict[str, Any]:
    """Aggregated click stats per partner + src (for the admin revenue card)."""
    pipeline = [
        {"$group": {
            "_id": {"partner": "$partner", "src": "$src"},
            "clicks": {"$sum": 1},
            "last_click": {"$max": "$ts"},
        }},
        {"$sort": {"clicks": -1}},
        {"$limit": 100},
    ]
    rows = await db.affiliate_clicks.aggregate(pipeline).to_list(length=100)
    totals_pipeline = [
        {"$group": {"_id": "$partner", "clicks": {"$sum": 1}}},
        {"$sort": {"clicks": -1}},
    ]
    totals = await db.affiliate_clicks.aggregate(totals_pipeline).to_list(length=50)
    grand_total = await db.affiliate_clicks.count_documents({})

    return {
        "total_clicks": grand_total,
        "by_partner": [{"partner": t["_id"], "clicks": t["clicks"]} for t in totals],
        "by_partner_src": [
            {
                "partner": r["_id"]["partner"],
                "src": r["_id"]["src"],
                "clicks": r["clicks"],
                "last_click": r["last_click"],
            }
            for r in rows
        ],
        "partner_urls": AFFILIATE_URLS,
    }


# Include the router in the main app
api_router.include_router(ati.build_ati_router(db, require_write_key))
api_router.include_router(proof.build_proof_router(db, require_write_key))
api_router.include_router(auth_module.build_auth_router(db))
api_router.include_router(analytics.build_analytics_router(db))
app.include_router(api_router)


@app.on_event("startup")
async def seed_auth() -> None:
    await auth_module.seed_admin(db)
    await db.users.create_index("email", unique=True)
    await db.user_sessions.create_index("session_token")
    await db.login_attempts.create_index("identifier")
    await db.analytics_visits.create_index([("visitor_id", 1), ("path", 1), ("date", 1)], unique=True)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
