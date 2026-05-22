"""
MNQ live market data feed.

Yahoo Finance CME endpoint returns real-time NQ futures.
NQ (E-mini) and MNQ (Micro) trade at the SAME PRICE — MNQ is 1/10 contract size.
So we fetch NQ=F and broadcast it as the MNQ tick.

Symbol mapping:
    TradingView      :  CME_MINI:MNQ1!    (continuous front month)
    NinjaTrader      :  MNQ MM-YY         (e.g. MNQ 03-26 = MNQH26)
    Yahoo Finance    :  NQ=F              (continuous front month, same price as MNQ)
    Our backend      :  MNQ
"""
import asyncio
import logging
import time
from typing import Dict, Optional, List

import httpx

logger = logging.getLogger(__name__)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/NQ=F"
HEADERS = {"User-Agent": "Mozilla/5.0 (MNQScalpStacks/1.0)"}

# Last known good tick (warm cache so first connect is instant)
_last_tick: Dict[str, float] = {
    "price": 0.0,
    "previous_close": 0.0,
    "change": 0.0,
    "change_percent": 0.0,
    "day_high": 0.0,
    "day_low": 0.0,
    "fetched_at": 0.0,
    "stale": True,
}

# Recent candle window for chart-aligned indicators (server-side fallback)
_minute_bars: List[dict] = []


async def _fetch_yahoo() -> Optional[dict]:
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                YAHOO_URL,
                params={"range": "1d", "interval": "1m"},
                headers=HEADERS,
            )
            r.raise_for_status()
            data = r.json()
            meta = data["chart"]["result"][0]["meta"]
            timestamps = data["chart"]["result"][0].get("timestamp", []) or []
            quote = data["chart"]["result"][0]["indicators"]["quote"][0]
            opens = quote.get("open", []) or []
            highs = quote.get("high", []) or []
            lows = quote.get("low", []) or []
            closes = quote.get("close", []) or []
            volumes = quote.get("volume", []) or []

            bars: List[dict] = []
            for i, ts in enumerate(timestamps):
                if i >= len(closes) or closes[i] is None:
                    continue
                bars.append({
                    "time": int(ts),
                    "open": float(opens[i]) if opens[i] is not None else float(closes[i]),
                    "high": float(highs[i]) if highs[i] is not None else float(closes[i]),
                    "low": float(lows[i]) if lows[i] is not None else float(closes[i]),
                    "close": float(closes[i]),
                    "volume": int(volumes[i]) if volumes[i] is not None else 0,
                })

            return {
                "price": float(meta["regularMarketPrice"]),
                "previous_close": float(meta.get("previousClose", meta["regularMarketPrice"])),
                "day_high": float(meta.get("regularMarketDayHigh", 0) or 0),
                "day_low": float(meta.get("regularMarketDayLow", 0) or 0),
                "currency": meta.get("currency", "USD"),
                "exchange": meta.get("exchangeName", "CME"),
                "market_state": meta.get("marketState", "UNKNOWN"),
                "bars": bars,
            }
    except Exception as e:
        logger.warning(f"yahoo fetch failed: {e}")
        return None


def _compute_indicators(bars: List[dict]) -> dict:
    """EMA9, EMA21, session VWAP, RSI14 from server-side bars (fallback when frontend chart hides them)."""
    if not bars:
        return {"ema9": 0.0, "ema21": 0.0, "vwap": 0.0, "rsi": 50.0}

    closes = [b["close"] for b in bars]

    def _ema(period: int) -> float:
        if len(closes) < period:
            return closes[-1]
        k = 2 / (period + 1)
        seed = sum(closes[:period]) / period
        for c in closes[period:]:
            seed = c * k + seed * (1 - k)
        return seed

    # Session VWAP across the entire day window
    cum_pv = cum_v = 0.0
    for b in bars:
        typ = (b["high"] + b["low"] + b["close"]) / 3
        cum_pv += typ * (b["volume"] or 1)
        cum_v += b["volume"] or 1
    vwap = cum_pv / cum_v if cum_v else closes[-1]

    # RSI14
    gains = losses = 0.0
    for i in range(1, min(15, len(closes))):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_g = gains / 14
    avg_l = losses / 14
    rs = avg_g / avg_l if avg_l else 100
    rsi = 100 - (100 / (1 + rs)) if avg_l else 70

    return {
        "ema9": round(_ema(9), 2),
        "ema21": round(_ema(21), 2),
        "vwap": round(vwap, 2),
        "rsi": round(rsi, 1),
    }


async def refresh_once() -> dict:
    """Pull fresh tick from Yahoo, update cache, return the snapshot."""
    data = await _fetch_yahoo()
    if not data:
        _last_tick["stale"] = True
        return get_last()

    bars = data["bars"]
    _minute_bars[:] = bars  # update cached bars

    indicators = _compute_indicators(bars)
    price = data["price"]
    prev = data["previous_close"]

    _last_tick.update({
        "symbol": "MNQ",
        "price": round(price, 2),
        "close": round(price, 2),
        "previous_close": round(prev, 2),
        "change": round(price - prev, 2),
        "change_percent": round((price - prev) / prev * 100 if prev else 0, 2),
        "day_high": round(data["day_high"], 2),
        "day_low": round(data["day_low"], 2),
        "currency": data["currency"],
        "exchange": data["exchange"],
        "market_state": data["market_state"],
        "source": "yahoo:NQ=F",
        "fetched_at": time.time(),
        "stale": False,
        **indicators,
    })
    return get_last()


def get_last() -> dict:
    """Return cached snapshot (does not network)."""
    return dict(_last_tick)


def get_bars() -> List[dict]:
    return list(_minute_bars)


# ---------- WebSocket broadcaster ----------

class TickBroker:
    """Fan-out WebSocket connections. Single fetcher → many subscribers."""

    def __init__(self) -> None:
        self._clients: set = set()
        self._task: Optional[asyncio.Task] = None
        self._poll_seconds: int = 3

    def register(self, ws) -> None:
        self._clients.add(ws)
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def unregister(self, ws) -> None:
        self._clients.discard(ws)

    async def _loop(self) -> None:
        while self._clients:
            try:
                snap = await refresh_once()
                dead = []
                for c in list(self._clients):
                    try:
                        await c.send_json(snap)
                    except Exception:
                        dead.append(c)
                for d in dead:
                    self._clients.discard(d)
            except Exception as e:
                logger.warning(f"tick loop error: {e}")
            await asyncio.sleep(self._poll_seconds)

broker = TickBroker()
