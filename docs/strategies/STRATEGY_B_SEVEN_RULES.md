# Strategy B — Outer Range Extremes (alerts only)

**Source (not in this git repo; cited for reviewers):** `/workspace/grubbot/strategy-b/01_outline.md` lines 32–45 (MQU-SB-001 V1.0, founder-approved per Zelator, Oct 21 2026) and `/workspace/grubbot/strategy-b/README.md` (PENDING parameters remain unapproved).

This evaluator implements only those seven rules. It **does not place orders**. Volume profile, order flow, and ES/MNQ intermarket alignment are optional context, not rules, and are not used to fire alerts.

## Seven rules (verbatim sense of 01_outline.md)

1. Identify the range on the **15m** chart: upper resistance and lower support.
2. Trade only extremes: upper boundary = evaluate shorts; lower boundary = evaluate longs; middle = WAIT.
3. Candlestick confirmation: evaluate engulfing patterns at the boundaries; a single wick is not sufficient.
4. Three-chart framework: 15m = range context + confirmation; 5m = directional bias + rejection; 1m = entry refinement. Conflict = WAIT.
5. Indicators (VWAP, **EMA 21**, RSI 14) are supporting evidence only; indicators alone never establish a setup.
6. Risk before entry: structural invalidation, dollar risk via correct contract specs; if the structural stop exceeds the risk limit, WAIT.
7. Exit and journal: define exit conditions before entry; record setup, confirmation, risk, and review. A disciplined WAIT counts as successful rule-following.

## Parameters — PENDING (do not invent)

Range-definition thresholds, engulfing validity window, risk-limit values, and exit framework remain **unapproved** (`08`, `10`, and `12_founder_decision_matrix.md`). The evaluator therefore:

- requires the 15m range high/low to be **supplied** (operator or test fixture) — it will not invent a range;
- will **not** emit a confirmation alert unless `STRATEGY_B_PARAMETERS_APPROVED=true` **and** `risk_limit_dollars` is provided;
- still returns a structured WAIT / disabled result so the dashboard can show why nothing fired.

MNQ contract math used only when a risk limit is supplied: **$2 per point per MNQ contract** (documented in the Strategy A report Gate 6; same CME spec).
