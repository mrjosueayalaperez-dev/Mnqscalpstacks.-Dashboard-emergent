from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import httpx
import asyncio
from emergentintegrations.llm.chat import LlmChat, UserMessage

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# API Keys
ALPHA_VANTAGE_KEY = os.environ.get('ALPHA_VANTAGE_KEY', 'demo')
EMERGENT_LLM_KEY = os.environ.get('EMERGENT_LLM_KEY')

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

# AI Analysis Routes
@api_router.post("/ai/analyze")
async def ai_analyze(request: AIAnalysisRequest):
    """Get AI-powered trade analysis"""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    # Fetch current data for the symbol
    quote = await fetch_stock_quote(request.symbol)
    indicators = await fetch_technical_indicators(request.symbol)
    
    system_message = """You are an expert trading analyst specializing in MNQ futures and momentum stocks ($1-$20 range). 
    Provide concise, actionable analysis. Focus on:
    - Entry/exit points based on technical indicators
    - Risk management (stop loss, position sizing)
    - Market context and momentum
    Be direct and specific. No financial advice disclaimers."""
    
    context_data = f"""
    Symbol: {request.symbol}
    Current Price: ${quote.get('price', 'N/A') if quote else 'N/A'}
    Change: {quote.get('change_percent', 'N/A')}%
    Volume: {quote.get('volume', 'N/A') if quote else 'N/A'}
    EMA 9: {indicators.get('ema9', 'N/A')}
    EMA 21: {indicators.get('ema21', 'N/A')}
    RSI (14): {indicators.get('rsi', 'N/A')}
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
