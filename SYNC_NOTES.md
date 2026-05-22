# MNQ Live Feed — Symbol & Architecture Notes

## The Desync You Hit (and the Fix)

**Before:** The cockpit price was `18,500` while TradingView showed `~29,520`.

**Root cause:**
1. `/api/futures/mnq` returned a **synthetic mock** seeded with a hardcoded baseline `18500.0`.
2. The lightweight-charts panel generated its own walk from that same fake base.
3. Order fills used the same hardcoded 18,500 as the simulated fill price.
4. None of these touched real market data, so they could never reflect TradingView.

**After (Feb 2026 fix):**
1. `/api/futures/mnq` now hits **Yahoo Finance NQ=F** in real time (CME continuous front month — NQ and MNQ trade at the *same price*; MNQ is just 1/10th contract size).
2. The chart panel is the **official TradingView Advanced Chart widget** pointing at `CME_MINI:MNQ1!`. This is the same data you see on tradingview.com — desync is mathematically impossible because it's the same data source rendered by TradingView themselves.
3. WebSocket `/api/ws/mnq` broadcasts new ticks ~every 3s to all connected operator cockpits (single fetcher, many subscribers).
4. Operator order fills now use the **live cached price**, so journal entries, P&L, and bracket SL/TP calculations all align with the real market.

## Symbol Mapping

| Surface         | Symbol             | Notes                                              |
| --------------- | ------------------ | -------------------------------------------------- |
| TradingView     | `CME_MINI:MNQ1!`   | Continuous front-month, auto-rolls each quarter    |
| NinjaTrader ATI | `MNQ 03-26`        | Quarterly format: `MMM YY`. March 2026 = MNQH26    |
| Yahoo Finance   | `NQ=F`             | E-mini front month; same price as MNQ              |
| Our backend     | `MNQ`              | Logical symbol; mapped to NQ=F upstream            |

### Quarterly Rollover
MNQ rolls every 3 months: **H** (Mar), **M** (Jun), **U** (Sep), **Z** (Dec).
TradingView's `MNQ1!` auto-rolls; Yahoo's `NQ=F` auto-rolls; **NinjaTrader does not** — when you wire Phase 2 you must rebuild the contract string each cycle (e.g. switch from `MNQ 03-26` → `MNQ 06-26` after Mar expiry).

A safe rule: when the cockpit detects today's date is within 5 trading days of expiry, the backend should flip the NinjaTrader symbol and emit a roll-over event in the journal.

## Live Feed Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│ Browser (React)                                                  │
│ ┌──────────────────────────────┐  ┌──────────────────────────┐   │
│ │ TradingView Advanced Widget  │  │ useMnqLive() hook        │   │
│ │  symbol: CME_MINI:MNQ1!      │  │  - WebSocket primary     │   │
│ │  studies: EMA9 EMA21 VWAP    │  │  - REST fallback every 8s│   │
│ │  Real-time CME feed          │  │  - Exponential reconnect │   │
│ └──────────────────────────────┘  └────────────┬─────────────┘   │
│        (visual ground truth)                   │                 │
└────────────────────────────────────────────────┼─────────────────┘
                                                 │ wss://…/api/ws/mnq
┌────────────────────────────────────────────────▼─────────────────┐
│ FastAPI backend                                                  │
│ ┌──────────────────────────────────────────────────────────────┐ │
│ │ TickBroker (single fan-out task)                             │ │
│ │   poll Yahoo every 3s → broadcast to all sockets             │ │
│ └──────────────────────────────────────────────────────────────┘ │
│        │                                                         │
│        ▼                                                         │
│ ┌──────────────────────────────┐  ┌──────────────────────────┐   │
│ │ /api/futures/mnq (REST)      │  │ /api/operator/order      │   │
│ │  returns last cached snap    │  │  uses live price as fill │   │
│ └──────────────────────────────┘  └──────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
                                                 │
                                                 ▼
                              Yahoo Finance NQ=F (CME real-time)
```

## Synchronization Safeguards

1. **Single source of truth:** Yahoo fetcher is the *only* writer of `_last_tick`. Order fills, REST snapshot, and WebSocket frames all read from the same cache.
2. **Stale-tick refusal:** If `get_last()` returns no price *and* a fresh fetch fails, `/api/operator/order` returns **503** instead of filling at a fake price.
3. **Visual ground truth:** TradingView widget bypasses our backend entirely for the chart — there is no scenario where the chart can lie.
4. **WS dropouts:** Frontend hook auto-reconnects with exponential backoff; REST poll every 8s keeps the panels alive even with no WebSocket.
5. **Cache freshness:** Each tick stamped with `fetched_at`; `stale: true` flag flips when Yahoo errors so the UI can warn the operator.

## What Was Removed / Deprecated

- `LiveChart.js` (lightweight-charts custom chart) — kept on disk but no longer mounted
- Synthetic candle generator and `MNQ_MOCK_BASE_PRICE` env var (never added — we went straight to real)
- The 4-second `setInterval(refreshMNQ, 4000)` REST polling — replaced by WebSocket primary

## Phase 2 Hand-off (NinjaTrader ATI)

When you wire the ATI bridge:
1. The cockpit's BUY/SELL flow already validates server-side. Add an `ati_writer.py` module that emits the OIF (`Documents/NinjaTrader 8/incoming/`) file *after* validation passes.
2. The OIF format we'll target: `PLACE;{account};{symbol};{side};{qty};MARKET;0;0;DAY;;{atm_template};{order_id};;;`
3. Phase 3 watches `outgoing/` for fills and reconciles them against the cockpit's local position state.
4. Until ATI is live, the cockpit's `position` field is the simulator's belief — broker truth wins when the bridge connects.
