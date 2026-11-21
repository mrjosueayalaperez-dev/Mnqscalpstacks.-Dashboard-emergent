# Bot B — Outer Range Extremes Signal Detector

**Specification v1.0 — November 15, 2026**
**Status: DOCUMENTATION / ENGINEERING PREP ONLY.** Branch-only development. Not merged, not deployed, no live execution. SIM / PAPER / TEST only.
**Authority:** MQU-SB-001 v1.0 "Outer Range Extremes" (founder approved, Oct 21, 2026) as recorded in `docs/strategies/STRATEGY_B_SEVEN_RULES.md`, and the Bot B Master Development Prompt v1.0 (founder, Nov 15, 2026). Where the master prompt and the approved Seven Rules differ, **the approved Seven Rules govern** until the founder rules otherwise; every divergence is listed in the Ambiguity Register (§6) and is never resolved silently in code.

---

## 1. What Bot B is

A standing, rule-based **detector** layered on the existing Strategy B evaluator (`backend/strategy_engine.py::evaluate_strategy_b`). On each newly completed bar it evaluates the market against the Seven Rules, classifies the result in the master prompt's five-state vocabulary, produces the full explanation record (§4 of the prompt), and appends the evaluation to an audit trail. It places no orders, connects to no execution endpoint, and — like the evaluator beneath it — **cannot emit a validated signal while `STRATEGY_B_PARAMETERS_APPROVED` is unset or any required parameter is missing.**

## 2. What already exists (Phase 1 inspection, Nov 15, 2026)

| Component | Location | State |
|---|---|---|
| Strategy B evaluator (Seven Rules R1–R7) | `backend/strategy_engine.py` `evaluate_strategy_b()` | IMPLEMENTED + TESTED (6 dedicated tests) |
| Rules + PENDING placeholders + approval flags | `backend/strategy_rules.py` | IMPLEMENTED |
| Indicator math (EMA, VWAP, RSI 14, bar aggregation) | `backend/strategy_engine.py` | IMPLEMENTED + TESTED |
| Engulfing detectors (bullish/bearish) | `backend/strategy_engine.py` | IMPLEMENTED + TESTED |
| Staleness gate (`snapshot_freshness`, fail-closed) | `backend/strategy_engine.py` (PR #21) | IMPLEMENTED + TESTED |
| Alert dedup identity (source + event_ts) | alert layer (PR #21) | IMPLEMENTED + TESTED |
| Market data | `backend/market_feed.py` — Yahoo NQ=F, **delayed ~10 min, always labeled delayed** | IMPLEMENTED |
| Notifications (Discord path) | `backend/notifications.py` | IMPLEMENTED (Bot B wiring = Phase 6, gated) |
| Seven Rules document | `docs/strategies/STRATEGY_B_SEVEN_RULES.md` | APPROVED v1.0 |

## 3. What Bot B adds (Phase 4 scope)

1. **Five-state classification** (master prompt §3): WAITING · POTENTIAL SETUP · CONFIRMATION PENDING · VALIDATED PAPER SIGNAL · NO TRADE — mapped from evaluator results (§5). The evaluator's own states (WAIT / CONFIRMED / DISABLED_PENDING_PARAMETERS) remain the internal source of truth.
2. **Explanation record builder** (prompt §4): the 14-field record for every evaluation, including conditions passed/failed lists and a plain-English explanation generated from the actual rule results — never free-invented.
3. **Detector loop + audit trail**: evaluate on newly completed bars only; record every evaluation (timestamp ET, inputs hash, classification, explanation) to an append-only audit log; suppress duplicate classifications using the existing dedup identity.
4. **Per-timeframe engulfing reporting**: engulfing status reported for both 15m and 5m in the explanation record (see Ambiguity A-1); classification follows the approved rules (15m confirmation) until the founder rules.

## 4. Strategy specification (as approved — the bot follows this, not its own invention)

1. **R1 Range (15m):** upper resistance and lower support must be **supplied** (operator or fixture). The bot never invents a range. Invalid range (high ≤ low) = NO TRADE with reason.
2. **R2 Extremes only:** upper boundary → evaluate SHORT; lower boundary → evaluate LONG; middle or mixed = WAITING. "At a boundary" uses the evaluator's existing no-invented-parameter logic: the bar interacts with the supplied level and price sits on that boundary's side of the range midpoint. No numeric near-zone width exists until approved.
3. **R3 Engulfing confirmation:** a qualifying engulfing pattern at the boundary (15m confirmation bar per the approved framework). A single wick is not sufficient.
4. **R4 Three-chart framework:** 15m = range context + confirmation; 5m = directional bias + rejection; 1m = entry refinement. Any conflict = WAITING (classification: NO TRADE when a mandatory condition has affirmatively failed; see §5 mapping).
5. **R5 Indicators supporting only:** VWAP, EMA21, RSI 14 are evidence, never a setup by themselves. EMA9 is reported as context (Ambiguity A-2). Volume is reported as observed; no approved volume threshold exists (Ambiguity A-5).
6. **R6 Risk before entry:** structural invalidation from recent 1m structure; dollar risk at the CME MNQ spec of $2.00 per point per contract. If `risk_limit_dollars` is not supplied, or the structural stop exceeds it → no validated signal.
7. **R7 Exits + journal before entry:** exit conditions must be supplied before any validated signal; every evaluation is journaled. A disciplined WAIT is successful rule-following.

**Data discipline:** delayed Yahoo data is labeled delayed in every record. Stale, incomplete, or malformed input is rejected (classification NO TRADE with the data reason, or WAITING when no evaluation is possible — never a fabricated value).

## 5. Classification mapping (evaluator → Bot B states)

| Situation | Bot B classification |
|---|---|
| No range supplied, or no bars yet | WAITING |
| Price in boundary half of range, not yet interacting with a boundary | POTENTIAL SETUP |
| At a boundary; some rules passed, confirmation incomplete (e.g., alignment pending, engulfing not yet formed on a completed bar) | CONFIRMATION PENDING |
| All Seven Rules pass **and** parameters approved **and** risk limit + exits supplied | VALIDATED PAPER SIGNAL |
| A mandatory condition affirmatively failed (invalid range, mid-range initiation attempt, engulfing failed on completed bars, timeframe conflict, stop over risk limit, stale/malformed data) | NO TRADE |
| All rules pass on the data but parameters NOT approved | CONFIRMATION PENDING with reason `DISABLED_PENDING_PARAMETERS` — **never** VALIDATED |

## 6. Ambiguity Register — founder decisions (nothing here is resolved in code until ruled)

- **A-1 Engulfing timeframe.** Master prompt §1 places the qualifying engulfing candle on the **5-minute** chart; approved Rule 4 and the existing evaluator place confirmation engulfing on the **15-minute** chart (5m = bias + rejection). *Interim:* classification follows the approved rules (15m); 5m engulfing is reported in the explanation record.
- **A-2 EMA9 role.** The prompt checks EMA9 + EMA21 "for market control"; approved Rule 5 names VWAP / EMA21 / RSI 14 as supporting evidence and does not name EMA9. *Interim:* EMA9 reported as context only; never gates.
- **A-3 VWAP directional veto.** The prompt states flat rules (no CALL below VWAP, no PUT above VWAP). At a range boundary, price is frequently on the far side of VWAP by construction, and Rule 5 makes VWAP supporting-only. A hard veto would contradict the boundary logic. *Interim:* VWAP position reported in every record; no hard veto beyond the approved rules.
- **A-4 "Established range" definition.** No approved numeric definition exists (session window, minimum touches, lookback). *Interim:* range is supplied, per R1 — the bot does not derive one.
- **A-5 Numeric parameters (the pending "Grobot" set).** Boundary approach tolerance, engulfing validity window (`engulfing_validity_window_bars`), volume confirmation threshold, risk limit dollars, exit framework — all PENDING in `strategy_rules.py` and the founder decision matrix. *Interim:* named, unset, and blocking where the rules require them.
- **A-6 NO TRADE vs WAITING boundary.** The prompt's NO TRADE = "one or more mandatory conditions failed." §5's mapping (affirmative failure vs not-yet-developed) is this spec's documented interpretation, open to founder correction.

## 7. Testing plan (Phase 5 — fixtures first, honesty about data)

The master prompt's eleven test cases map onto the evaluator's existing fixture style: upper boundary, lower boundary, middle, false engulfing, valid engulfing, VWAP conflict, EMA conflict, missing data, delayed/stale data, incomplete entry confirmation, duplicate signals. Each test records expected vs actual. **No historical MNQ bar archive exists in this repository**; Phase 5 runs on constructed fixtures and any recorded snapshots available, and reports will say exactly that — fixture results are never presented as live-market validation. Phase 7 (manual chart verification) remains the founder's chart-side check.

## 8. Governance

Branch-only (`feature/bot-b-outer-range-extremes`). Strategy A untouched. No merge, no deploy, no purchases, no credentials, no live endpoints. Every phase reports: files changed, tests run with actual results, and status as IMPLEMENTED / TESTED / DEPLOYED — never upgraded beyond evidence.

*Knowledge Is The Legacy. M&Q does not chase trades. M&Q waits for evidence.*
