# Strategy A — Six Gates (alerts only)

**Source (not in this git repo; cited for reviewers):** `/workspace/tv/strategy_a_report.md` (sections “Gate logic” and “Inputs and defaults”), plus `/workspace/tv/strategy_a_six_gates.pine`.

This backend evaluator follows that written design. It **does not place orders**.

## Gates (documented)

1. **Location** — price interacts with a center S/R zone (manual center, or prior-day midpoint when center is 0). Zone width is an input.
2. **Activity** — volume spike vs SMA, rejection wick, or strong-body momentum bar.
3. **Candle close** — only a completed bar is evaluated.
4. **Retest / no-chase** — price left the zone, returned, and held; bar range ≤ ATR × k; distance from EMA 9 ≤ max.
5. **Alignment** — 15-minute confirmation, then 5-minute bias, then 1-minute entry. Direction is close vs **EMA 21 and VWAP** (both must agree) on each timeframe. ES alignment is documented; extra RSI evidence is allowed on divergence. EMA 9, EMA 21, and VWAP are labeled under those names (not EMA20 / EMA50 proxies).
6. **Risk** — structural invalidation (swing high/low). Pass only when stop distance is within the max-risk input.

**Hard VWAP rule:** no LONG confirmation when close < VWAP; no SHORT confirmation when close > VWAP.

## Parameters — PENDING

The numeric defaults in the source report are **inputs / assumptions, not founder-approved production values**. They are stored here as explicit placeholders and the evaluator **will not emit a confirmation alert** unless `STRATEGY_A_PARAMETERS_APPROVED=true` (Josue sets this after approving the numbers). Callers may pass a params dict in tests.

Placeholder defaults taken from `strategy_a_report.md` §2 (for tests and preview only):

| Key | Placeholder | Report role |
|---|---|---|
| zone_width_points | 15.0 | Gate 1 zone |
| volume_sma_length | 20 | Gate 2 |
| volume_spike_multiple | 1.5 | Gate 2 |
| rejection_wick_ratio | 0.5 | Gate 2 |
| strong_body_ratio | 0.6 | Gate 2 |
| left_zone_lookback | 10 | Gate 4 |
| atr_length | 14 | Gate 4 |
| no_chase_atr_k | 1.5 | Gate 4 |
| no_chase_ema9_max_points | 20.0 | Gate 4 |
| rsi_length | 14 | Gate 5 |
| rsi_long_extra | 55.0 | Gate 5 divergence |
| rsi_short_extra | 45.0 | Gate 5 divergence |
| ema_fast | 9 | EMA 9 |
| ema_slow | 21 | EMA 21 |
| max_risk_points | (unset) | Gate 6 — PENDING, no silent default fire |
