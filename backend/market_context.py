"""Market context — prior-day H/L, ADR, range expansion, momentum proxy."""
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

YAHOO_URL = "https://query1.finance.yahoo.com/v8/finance/chart/NQ=F"
HEADERS = {"User-Agent": "Mozilla/5.0 (MNQScalpStacks/1.0)"}


async def get_market_context() -> Optional[dict]:
    """Multi-day MNQ context: prior day H/L, ADR(5), today's range, momentum."""
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            r = await client.get(
                YAHOO_URL,
                params={"range": "10d", "interval": "1d"},
                headers=HEADERS,
            )
            r.raise_for_status()
            data = r.json()
            res = data["chart"]["result"][0]
            meta = res["meta"]
            quote = res["indicators"]["quote"][0]
            highs = [h for h in (quote.get("high") or []) if h is not None]
            lows = [l for l in (quote.get("low") or []) if l is not None]
            closes = [c for c in (quote.get("close") or []) if c is not None]
            opens = [o for o in (quote.get("open") or []) if o is not None]
            volumes = [v for v in (quote.get("volume") or []) if v is not None]

            if len(closes) < 2:
                return None

            today_open = opens[-1] if opens else closes[-1]
            today_high = highs[-1] if highs else closes[-1]
            today_low = lows[-1] if lows else closes[-1]
            current = float(meta["regularMarketPrice"])

            # Prior day = most recent COMPLETED session = index -2
            prior_high = highs[-2]
            prior_low = lows[-2]
            prior_close = closes[-2]
            prior_range = prior_high - prior_low

            # ADR(5) = average daily range over last 5 completed sessions
            ranges = [(highs[i] - lows[i]) for i in range(max(0, len(highs) - 6), len(highs) - 1)]
            adr5 = sum(ranges) / len(ranges) if ranges else 0

            today_range = today_high - today_low
            range_pct = (today_range / adr5 * 100) if adr5 else 0

            # Position within today's range (0% = at low, 100% = at high)
            pos_in_day = ((current - today_low) / today_range * 100) if today_range else 50

            # Distance from PDH / PDL in ticks (MNQ 1 tick = 0.25 pts)
            ticks_from_pdh = round((current - prior_high) / 0.25, 1)
            ticks_from_pdl = round((current - prior_low) / 0.25, 1)

            # Simple momentum proxy: today's close-on-volume vs 5d avg volume
            avg_vol_5d = sum(volumes[-6:-1]) / 5 if len(volumes) >= 6 else (volumes[-1] if volumes else 0)
            today_vol = volumes[-1] if volumes else 0
            volume_strength_pct = (today_vol / avg_vol_5d * 100) if avg_vol_5d else 0

            # Trend bias from last 5 daily closes
            recent_closes = closes[-5:]
            close_change = (current - recent_closes[0]) / recent_closes[0] * 100 if recent_closes else 0

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
                "ticks_from_pdh": ticks_from_pdh,
                "ticks_from_pdl": ticks_from_pdl,
                "pos_in_day_pct": round(pos_in_day, 1),
                "adr5": round(adr5, 2),
                "range_expansion_pct": round(range_pct, 1),
                "volume_strength_pct": round(volume_strength_pct, 1),
                "trend_5d_pct": round(close_change, 2),
                "is_range_extended": range_pct > 110,
                "is_above_pdh": ticks_from_pdh > 0,
                "is_below_pdl": ticks_from_pdl < 0,
                "source": "yahoo:NQ=F (10d daily)",
            }
    except Exception as e:
        logger.warning(f"market context fetch failed: {e}")
        return None
