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
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

YAHOO_URL: str = "https://query1.finance.yahoo.com/v8/finance/chart/NQ=F"
HEADERS: Dict[str, str] = {"User-Agent": "Mozilla/5.0 (MNQScalpStacks/1.0)"}

# Last known good tick (warm cache so first connect is instant)
_last_tick: Dict[str, Any] = {
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
_minute_bars: List[Dict[str, Any]] = []


def _safe_float(v: Any, fallback: float = 0.0) -> float:
    """None-safe float coerce."""
    if v is None:
        return fallback
    try:
        return float(v)
    except (TypeError, ValueError):
        return fallback


def _build_bars(timestamps: List[int], q: Dict[str, List]) -> List[Dict[str, Any]]:
    """Zip Yahoo's parallel OHLCV arrays into bar dicts. Skips bars with no close."""
    opens = q.get("open", []) or []
    highs = q.get("high", []) or []
    lows = q.get("low", []) or []
    closes = q.get("close", []) or []
    volumes = q.get("volume", []) or []

    bars: List[Dict[str, Any]] = []
    for i, ts in enumerate(timestamps):
        if i >= len(closes) or closes[i] is None:
            continue
        close = float(closes[i])
        bars.append({
            "time": int(ts),
            "open": _safe_float(opens[i] if i < len(opens) else None, close),
            "high": _safe_float(highs[i] if i < len(highs) else None, close),
            "low": _safe_float(lows[i] if i < len(lows) else None, close),
            "close": close,
            "volume": int(volumes[i]) if i < len(volumes) and volumes[i] is not None else 0,
        })
    return bars


def _parse_yahoo_response(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Pull meta + OHLCV out of Yahoo's nested response. Returns None on shape mismatch."""
    try:
        result = payload["chart"]["result"][0]
        meta = result["meta"]
        timestamps = result.get("timestamp", []) or []
        quote = result["indicators"]["quote"][0]
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"yahoo response shape invalid: {e}")
        return None

    price = _safe_float(meta.get("regularMarketPrice"))
    return {
        "price": price,
        "previous_close": _safe_float(meta.get("previousClose"), price),
        "day_high": _safe_float(meta.get("regularMarketDayHigh")),
        "day_low": _safe_float(meta.get("regularMarketDayLow")),
        "currency": meta.get("currency", "USD"),
        "exchange": meta.get("exchangeName", "CME"),
        "market_state": meta.get("marketState", "UNKNOWN"),
        "bars": _build_bars(timestamps, quote),
    }


async def _fetch_yahoo() -> Optional[Dict[str, Any]]:
    """Single network call to Yahoo's chart endpoint. Parsing handled by helpers."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(YAHOO_URL, params={"range": "1d", "interval": "1m"}, headers=HEADERS)
            r.raise_for_status()
            data = _parse_yahoo_response(r.json())
            if data and not data["bars"]:
                # Non-trading day: 1d comes back empty — pull the last session instead
                r2 = await client.get(YAHOO_URL, params={"range": "5d", "interval": "1m"}, headers=HEADERS)
                r2.raise_for_status()
                d2 = _parse_yahoo_response(r2.json())
                if d2 and d2["bars"]:
                    cutoff = d2["bars"][-1]["time"] - 86400
                    data["bars"] = [b for b in d2["bars"] if b["time"] > cutoff]
            return data
    except Exception as e:
        logger.warning(f"yahoo fetch failed: {e}")
        return None


def _compute_indicators(bars: List[Dict[str, Any]]) -> Dict[str, float]:
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


async def refresh_once() -> Dict[str, Any]:
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


def get_last() -> Dict[str, Any]:
    """Return cached snapshot (does not network)."""
    return dict(_last_tick)


def get_bars() -> List[Dict[str, Any]]:
    return list(_minute_bars)


# ---------- WebSocket broadcaster ----------

class TickBroker:
    """Fan-out WebSocket connections. Single fetcher → many subscribers."""

    def __init__(self) -> None:
        self._clients: set = set()
        self._task: Optional[asyncio.Task] = None
        self._poll_seconds: int = 3

    def register(self, ws: Any) -> None:
        self._clients.add(ws)
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._loop())

    def unregister(self, ws: Any) -> None:
        self._clients.discard(ws)

    async def _loop(self) -> None:
        while self._clients:
            try:
                snap = await refresh_once()
                dead: List[Any] = []
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


broker: TickBroker = TickBroker()
