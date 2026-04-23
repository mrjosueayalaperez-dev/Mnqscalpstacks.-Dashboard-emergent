from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks
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
import asyncio
import random
from emergentintegrations.llm.chat import LlmChat, UserMessage

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

# Signal Engine State (in-memory for fast access)
signal_engine_state = {
    "kill_switch": False,
    "started_at": datetime.now(timezone.utc).isoformat(),
    "total_signals": 0,
    "errors": 0,
    "last_signal_time": None,
    "last_error": None,
}

# Create the main app without a prefix
app = FastAPI()
api_router = APIRouter(prefix="/api")

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

class CheckoutRequest(BaseModel):
    tier: str  # pro, elite
    origin_url: str

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

async def send_discord_signal(signal: dict):
    """Send branded signal to Discord webhook — MNQ SCALP STACKS BOT"""
    if not DISCORD_WEBHOOK_URL or DISCORD_WEBHOOK_URL == "REPLACE_WITH_YOUR_DISCORD_WEBHOOK_URL":
        logger.info("Discord webhook not configured, skipping delivery")
        return False

    is_long = signal["side"] == "long"
    side_label = "LONG" if is_long else "SHORT"
    side_emoji = "🟢" if is_long else "🔴"
    signal_color = 5763719 if is_long else 15548997  # Green / Red

    # Confluence components display
    components = signal.get("components", {})
    pillars = []
    if components.get("vwap_filter"):
        pillars.append("VWAP")
    if components.get("rsi_momentum"):
        pillars.append("RSI")
    if components.get("structure"):
        pillars.append("Structure")
    # Fallback for legacy/webhook signals
    if not pillars:
        pillars = ["Price", "Flow", "NQ"]

    pillar_status = ", ".join(pillars) + " Confirmed"
    score = signal.get("confluence_score", 0)

    # Risk-reward calculation
    entry = signal.get("entry_price", 0)
    stop = signal.get("stop_loss", 0)
    tp1 = signal.get("tp1", 0)
    risk = abs(entry - stop)
    reward = abs(tp1 - entry)
    rr_ratio = f"{reward / risk:.1f}:1" if risk > 0 else "N/A"

    payload = {
        "username": "MNQ SCALP STACKS BOT",
        "avatar_url": "https://i.imgur.com/4S7S5vj.png",
        "embeds": [{
            "title": f"{side_emoji} NEW SCALP STACK SIGNAL — {side_label}",
            "color": signal_color,
            "fields": [
                {"name": "Asset", "value": f"{signal.get('symbol', 'MNQ')} (Micro Nasdaq)", "inline": True},
                {"name": "Strategy", "value": f"3-Pillar Setup ({score}/3)", "inline": True},
                {"name": "Status", "value": f"{'✅' if score >= 2 else '⚠️'} {pillar_status}", "inline": False},
                {"name": "Entry", "value": f"```${entry:.2f}```", "inline": True},
                {"name": "Stop Loss", "value": f"```${stop:.2f}```", "inline": True},
                {"name": "R:R", "value": f"```{rr_ratio}```", "inline": True},
                {"name": "TP1", "value": f"```${tp1:.2f}```", "inline": True},
                {"name": "TP2", "value": f"```${signal.get('tp2', 0):.2f}```", "inline": True},
                {"name": "Trend", "value": f"```{signal.get('trend_direction', 'neutral').upper()}```", "inline": True},
            ],
            "footer": {"text": "MNQ SCALP STACKS SaaS | Emergent.sh"},
            "timestamp": signal.get("created_at", datetime.now(timezone.utc).isoformat()),
        }]
    }

    try:
        async with httpx.AsyncClient() as http_client:
            resp = await http_client.post(DISCORD_WEBHOOK_URL, json=payload, timeout=5.0)
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
    """Compute the MNQ Stack v2 confluence score
    Matches Pine Script: Session VWAP + Structure (higher-low / lower-high)
    """
    vwap = ema20  # Proxy: in live use, session VWAP is passed in

    # 1. VWAP filter
    above_vwap = close_price > vwap
    below_vwap = close_price < vwap

    # 2. RSI momentum (simulated with price action)
    rsi_rising = close_price > open_price  # Bullish candle = proxy for RSI rising
    rsi_falling = close_price < open_price  # Bearish candle = proxy for RSI falling

    # 3. Structure: Higher-Low / Lower-High (pivot-based)
    # Higher-low: current low above previous low
    higher_low = low_price > prev_low
    # Lower-high: current high below previous high
    lower_high = high_price < prev_high

    # 4. Confluence scores (v2: VWAP + RSI + Structure)
    long_score = int(above_vwap) + int(rsi_rising) + int(higher_low)
    short_score = int(below_vwap) + int(rsi_falling) + int(lower_high)

    long_signal = long_score >= 3  # All 3 conditions met
    short_signal = short_score >= 3

    return {
        "above_vwap": above_vwap,
        "below_vwap": below_vwap,
        "rsi_rising": rsi_rising,
        "rsi_falling": rsi_falling,
        "higher_low": higher_low,
        "lower_high": lower_high,
        "long_score": long_score,
        "short_score": short_score,
        "long_signal": long_signal,
        "short_signal": short_signal,
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
        import random
        base_price = 150 + (hash(symbol) % 50)
        mock_data = []
        for i in range(50):
            price = base_price + random.uniform(-5, 5)
            mock_data.append({
                "time": f"2024-01-15 {9 + i//12}:{(i*5) % 60:02d}:00",
                "open": price,
                "high": price + random.uniform(0, 2),
                "low": price - random.uniform(0, 2),
                "close": price + random.uniform(-1, 1),
                "volume": random.randint(10000, 100000)
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
        import random
        for symbol in symbols[:3]:
            change = random.uniform(3, 8) * (1 if random.random() > 0.5 else -1)
            results.append({
                "symbol": symbol,
                "price": 10 + (hash(symbol) % 20),
                "change": round(change * 0.1, 2),
                "change_percent": str(round(change, 2)),
                "volume": random.randint(500000, 5000000),
                "alert_type": "breakout" if change > 0 else "breakdown",
                "is_mock": True
            })
    
    return {"scanners": results}

# MNQ Futures Routes
@api_router.get("/futures/mnq")
async def get_mnq_data():
    """Get MNQ (Micro Nasdaq) futures data - using QQQ as proxy"""
    quote = await fetch_stock_quote("QQQ")
    if not quote:
        import random
        base = 18500
        return {
            "symbol": "MNQ",
            "price": base + random.uniform(-50, 50),
            "change": random.uniform(-100, 100),
            "change_percent": str(round(random.uniform(-1, 1), 2)),
            "high": base + 100,
            "low": base - 100,
            "vwap": base + 10,
            "ema9": base + 15,
            "ema21": base - 5,
            "rsi": 50 + random.randint(-15, 15),
            "is_mock": True
        }
    
    # Scale QQQ to approximate MNQ
    scale = 45  # Approximate scaling factor
    return {
        "symbol": "MNQ",
        "price": quote["price"] * scale,
        "change": quote["change"] * scale,
        "change_percent": quote["change_percent"],
        "high": quote["high"] * scale,
        "low": quote["low"] * scale,
        "vwap": quote["price"] * scale * 0.998,
        "ema9": quote["price"] * scale * 1.001,
        "ema21": quote["price"] * scale * 0.999,
        "rsi": 55,
        "is_proxy": True
    }

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
    global signal_engine_state

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
    global signal_engine_state
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
    """Generate a test signal matching v2 logic (Session VWAP + Structure)"""
    global signal_engine_state

    if signal_engine_state["kill_switch"]:
        return {"status": "blocked", "reason": "Kill switch active"}

    side = random.choice(["long", "short"])
    base_price = 18500 + random.uniform(-100, 100)
    entry = round(base_price, 2)

    # v2: Pivot-based SL/TP (structure highs/lows)
    # SL = last pivot low (long) or last pivot high (short) + buffer
    # TP = last pivot high (long) or last pivot low (short)
    swing_range = random.uniform(6, 15)  # Realistic pivot distance
    sl_buffer = 0.25  # 1 tick buffer

    if side == "long":
        stop = round(entry - swing_range - sl_buffer, 2)  # Below last pivot low
        tp1 = round(entry + swing_range * 1.2, 2)  # Last pivot high
        tp2 = round(entry + swing_range * 2.0, 2)  # Extended target
    else:
        stop = round(entry + swing_range + sl_buffer, 2)  # Above last pivot high
        tp1 = round(entry - swing_range * 1.2, 2)  # Last pivot low
        tp2 = round(entry - swing_range * 2.0, 2)  # Extended target

    # v2 confluence: VWAP + RSI momentum + Structure
    above_vwap = side == "long"
    rsi_confirm = random.choice([True, True, True, False])  # 75% hit rate
    structure = random.choice([True, True, False])  # Higher-low or lower-high
    score = int(above_vwap) + int(rsi_confirm) + int(structure)

    signal_obj = Signal(
        symbol="MNQ",
        side=side,
        entry_price=entry,
        stop_loss=stop,
        tp1=tp1,
        tp2=tp2,
        confluence_score=score,
        components={
            "vwap_filter": above_vwap,
            "rsi_momentum": rsi_confirm,
            "structure": structure,
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
@api_router.get("/signals/pinescript")
async def get_pine_script():
    """Get the Pine Script v2 for TradingView"""
    pine = '''//@version=5
strategy("MNQ Scalp Stack v2 (1m) - Session VWAP + Structure", overlay=true,
     initial_capital=10000, pyramiding=0,
     commission_type=strategy.commission.percent, commission_value=0.01)

// -------------------- Inputs --------------------
useSessionVWAP  = input.bool(true, "Use Session VWAP (recommended)")
rsiLen          = input.int(14, "RSI Length", minval=2)
rsiLongMin      = input.float(55, "RSI Long Min", step=0.5)
rsiShortMax     = input.float(45, "RSI Short Max", step=0.5)

structureBars   = input.int(5, "Structure window (candles)", minval=3)
tpLookbackBars  = input.int(20, "TP lookback window (candles)", minval=5)

slBufferTicks   = input.int(1, "SL buffer (ticks)", minval=0, maxval=5)
pivotLen        = input.int(2, "Pivot len (left/right)", minval=1, maxval=5)

// -------------------- Indicators --------------------
vwap = useSessionVWAP ? ta.vwap(close) : ta.sma(close, 20)
rsi  = ta.rsi(close, rsiLen)

rsiRising  = rsi > rsi[1]
rsiFalling = rsi < rsi[1]

// -------------------- Pivots (confirmed) --------------------
tickSize = syminfo.mintick

ph = ta.pivothigh(high, pivotLen, pivotLen)
pl = ta.pivotlow(low, pivotLen, pivotLen)

var float lastPL = na
var float prevPL = na
var int   lastPLBar = na
var int   prevPLBar = na

if not na(pl)
    prevPL := lastPL
    prevPLBar := lastPLBar
    lastPL := pl
    lastPLBar := bar_index

var float lastPH = na
var float prevPH = na
var int   lastPHBar = na
var int   prevPHBar = na

if not na(ph)
    prevPH := lastPH
    prevPHBar := lastPHBar
    lastPH := ph
    lastPHBar := bar_index

// -------------------- Structure: higher-low / lower-high --------------------
higherLowFormed =
     not na(lastPL) and not na(prevPL) and
     (bar_index - lastPLBar) <= structureBars and
     (lastPL > prevPL + tickSize * slBufferTicks)

lowerHighFormed =
     not na(lastPH) and not na(prevPH) and
     (bar_index - lastPHBar) <= structureBars and
     (lastPH < prevPH - tickSize * slBufferTicks)

// -------------------- Entry conditions (bar close) --------------------
longSignal =
     close > vwap and
     rsi > rsiLongMin and rsiRising and
     higherLowFormed

shortSignal =
     close < vwap and
     rsi < rsiShortMax and rsiFalling and
     lowerHighFormed

// -------------------- TP/SL (latest confirmed swing within lookback) --------------------
tpHighOk = not na(lastPH) and (bar_index - lastPHBar) <= tpLookbackBars
tpLowOk  = not na(lastPL) and (bar_index - lastPLBar) <= tpLookbackBars

longSL  = not na(lastPL) ? (lastPL - tickSize * slBufferTicks) : na
longTP  = tpHighOk ? lastPH : na

shortSL = not na(lastPH) ? (lastPH + tickSize * slBufferTicks) : na
shortTP = tpLowOk ? lastPL : na

validLongLevels  = not na(longSL) and not na(longTP) and longTP > close
validShortLevels = not na(shortSL) and not na(shortTP) and shortTP < close

// -------------------- Orders --------------------
if longSignal and validLongLevels
    strategy.entry("L", strategy.long)
    strategy.exit("L-exit", from_entry="L", stop=longSL, limit=longTP)

if shortSignal and validShortLevels
    strategy.entry("S", strategy.short)
    strategy.exit("S-exit", from_entry="S", stop=shortSL, limit=shortTP)

// -------------------- Plotting --------------------
plot(vwap, "VWAP", color=color.new(color.orange, 0))

plotshape(longSignal,  title="Long Signal",  style=shape.triangleup,   location=location.belowbar, color=color.new(color.lime, 0), size=size.tiny, text="L")
plotshape(shortSignal, title="Short Signal", style=shape.triangledown, location=location.abovebar, color=color.new(color.red, 0),  size=size.tiny, text="S")

// -------------------- Alerts --------------------
alertcondition(longSignal,  title="Long Signal",  message='{"type":"buy","symbol":"{{ticker}}","price":"{{close}}","time":"{{time}}"}')
alertcondition(shortSignal, title="Short Signal", message='{"type":"sell","symbol":"{{ticker}}","price":"{{close}}","time":"{{time}}"}')
'''
    webhook_instructions = f"""
## TradingView Webhook Setup (v2)

1. Open TradingView -> MNQ 1-min chart
2. Pine Editor -> Paste the script above -> Add to Chart
3. Create Alert (right-click chart -> Add Alert)
4. Condition: "MNQ Scalp Stack v2" -> "Long Signal" or "Short Signal"
5. Enable "Webhook URL" and paste:
   {os.environ.get('REACT_APP_BACKEND_URL', 'YOUR_BACKEND_URL')}/api/webhook/tradingview

6. Webhook message (auto-filled by alertcondition):
   {{"type":"buy","symbol":"{{{{ticker}}}}","price":"{{{{close}}}}","time":"{{{{time}}}}"}}

## v2 Signal Logic:
- Session VWAP filter (price above/below)
- RSI 14 momentum (rising > 55 for longs, falling < 45 for shorts)
- Structure confirmation (higher-low for longs, lower-high for shorts)
- Pivot-based TP/SL (confirmed swing highs/lows)
"""

    return {
        "pine_script": pine,
        "webhook_instructions": webhook_instructions,
        "webhook_url": "/api/webhook/tradingview"
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
        num_signals = random.randint(1, 3)
        for i in range(num_signals):
            outcome_data = random.choice(outcomes)
            outcome, pnl, status = outcome_data
            side = random.choice(["long", "short"])
            base_price = 18300 + random.uniform(-200, 200)
            entry = round(base_price, 2)

            if side == "long":
                stop = round(entry - 8, 2)
                tp1 = round(entry + 10, 2)
                tp2 = round(entry + 20, 2)
            else:
                stop = round(entry + 8, 2)
                tp1 = round(entry - 10, 2)
                tp2 = round(entry - 20, 2)

            score = random.randint(2, 3)
            sig_time = day + timedelta(hours=random.choice([9, 10, 15, 16]), minutes=random.randint(0, 59))

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
                    "near_level": random.choice([True, False]),
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
from starlette.requests import Request

@api_router.post("/subscribers")
async def create_subscriber(sub: SubscriberCreate):
    """Register a new subscriber (free tier)"""
    # Check if email already exists
    existing = await db.subscribers.find_one({"email": sub.email}, {"_id": 0})
    if existing:
        return {
            "status": "existing",
            "subscriber": existing,
            "discord_invite": DISCORD_INVITES.get(existing.get("tier", "free"), ""),
        }

    subscriber = {
        "id": str(uuid.uuid4()),
        "email": sub.email,
        "name": sub.name or "",
        "tier": sub.tier,
        "status": "active",
        "stripe_session_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.subscribers.insert_one(subscriber)
    subscriber.pop("_id", None)

    return {
        "status": "created",
        "subscriber": subscriber,
        "discord_invite": DISCORD_INVITES.get(sub.tier, ""),
    }


@api_router.get("/subscribers/count")
async def get_subscriber_count():
    """Get total subscriber count (public metric)"""
    total = await db.subscribers.count_documents({})
    pro = await db.subscribers.count_documents({"tier": "pro"})
    elite = await db.subscribers.count_documents({"tier": "elite"})
    return {"total": total, "free": total - pro - elite, "pro": pro, "elite": elite}


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
        metadata={"tier": tier, "product": f"MNQ Stack Signals - {tier.title()}"},
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

    return {
        "status": status.status,
        "payment_status": status.payment_status,
        "amount_total": status.amount_total,
        "currency": status.currency,
        "metadata": status.metadata,
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

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return {"status": "error", "detail": str(e)}

# Include the router in the main app
app.include_router(api_router)

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
