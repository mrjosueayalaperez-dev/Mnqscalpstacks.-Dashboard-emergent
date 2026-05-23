"""Market context — prior-day H/L, ADR, range expansion, momentum proxy."""
import logging
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger(__name__)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/NQ=F"
HEADERS = {"User-Agent": "Mozilla/5.0 (MNQScalpStacks/1.0)"}


async def _fetch_daily_bars() -> Optional[Dict[str, Any]]:
    """Fetch 10-day daily OHLCV from Yahoo. Returns None on transport error."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                YAHOO_URL,
                params={"range": "10d", "interval": "1d"},
                headers=HEADERS,
            )
            r.raise_for_status()
            return r.json()
    except Exception as e:
        logger.warning(f"yahoo daily fetch failed: {e}")
        return None


def _extract_quote_series(payload: Dict[str, Any]) -> Optional[Dict[str, List]]:
    """Pull OHLCV arrays out of Yahoo's nested response. Returns None if shape is bad."""
    try:
        res = payload["chart"]["result"][0]
        quote = res["indicators"]["quote"][0]
        closes = [c for c in (quote.get("close") or []) if c is not None]
        if len(closes) < 2:
            return None
        return {
            "meta": res["meta"],
            "opens":   [o for o in (quote.get("open")   or []) if o is not None],
            "highs":   [h for h in (quote.get("high")   or []) if h is not None],
            "lows":    [l for l in (quote.get("low")    or []) if l is not None],
            "closes":  closes,
            "volumes": [v for v in (quote.get("volume") or []) if v is not None],
        }
    except (KeyError, IndexError, TypeError) as e:
        logger.warning(f"quote series shape invalid: {e}")
        return None


def _compute_adr(highs: List[float], lows: List[float], window: int = 5) -> float:
    """Average daily range across the last `window` completed sessions."""
    ranges = [(highs[i] - lows[i]) for i in range(max(0, len(highs) - window - 1), len(highs) - 1)]
    return sum(ranges) / len(ranges) if ranges else 0


def _volume_strength(volumes: List[int]) -> float:
    """Today's volume as % of 5-day average."""
    if len(volumes) < 6:
        return 0
    avg_5d = sum(volumes[-6:-1]) / 5
    today = volumes[-1] if volumes else 0
    return (today / avg_5d * 100) if avg_5d else 0


def _trend_change_pct(closes: List[float], current: float) -> float:
    """5-day percentage change from earliest close to current price."""
    recent = closes[-5:]
    return ((current - recent[0]) / recent[0] * 100) if recent and recent[0] else 0


def _ticks_from(current: float, level: float, tick_size: float = 0.25) -> float:
    return round((current - level) / tick_size, 1)


def _build_context(series: Dict[str, List]) -> Dict[str, Any]:
    """Pure transform: raw OHLCV → cockpit context payload."""
    meta = series["meta"]
    highs, lows, closes = series["highs"], series["lows"], series["closes"]
    opens, volumes = series["opens"], series["volumes"]

    current = float(meta["regularMarketPrice"])
    today_open = opens[-1] if opens else closes[-1]
    today_high = highs[-1] if highs else closes[-1]
    today_low  = lows[-1] if lows else closes[-1]

    # Prior session = index -2 (most recent COMPLETED session)
    prior_high  = highs[-2]
    prior_low   = lows[-2]
    prior_close = closes[-2]
    prior_range = prior_high - prior_low

    adr5 = _compute_adr(highs, lows, window=5)
    today_range = today_high - today_low
    range_pct = (today_range / adr5 * 100) if adr5 else 0
    pos_in_day = ((current - today_low) / today_range * 100) if today_range else 50

    ticks_pdh = _ticks_from(current, prior_high)
    ticks_pdl = _ticks_from(current, prior_low)

    return {
        "current": round(current, 2),
        "prior_high": round(prior_high, 2),
        "prior_low": round(prior_low, 2),
        "prior_close": round(prior_close, 2),
        "prior_range_points": round(prior_range, 2),
        "today_open": round(today_open, 2),
        "today_high": round(today_high, 2),
        "today_low": round(today_low, 2),
        "today_range_points": round(today_range, 2),
        "ticks_from_pdh": ticks_pdh,
        "ticks_from_pdl": ticks_pdl,
        "pos_in_day_pct": round(pos_in_day, 1),
        "adr5": round(adr5, 2),
        "range_expansion_pct": round(range_pct, 1),
        "volume_strength_pct": round(_volume_strength(volumes), 1),
        "trend_5d_pct": round(_trend_change_pct(closes, current), 2),
        "is_range_extended": range_pct > 110,
        "is_above_pdh": ticks_pdh > 0,
        "is_below_pdl": ticks_pdl < 0,
        "source": "yahoo:NQ=F (10d daily)",
    }


async def get_market_context() -> Optional[Dict[str, Any]]:
    """Multi-day MNQ context: prior day H/L, ADR(5), today's range, momentum."""
    payload = await _fetch_daily_bars()
    if not payload:
        return None
    series = _extract_quote_series(payload)
    if not series:
        return None
    try:
        return _build_context(series)
    except Exception as e:
        logger.warning(f"market context build failed: {e}")
        return None
