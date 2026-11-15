# Bot B — Phase 4 Implementation Notes (Nov 15, 2026)

Branch: `feature/bot-b-outer-range-extremes`. SIM / PAPER / TEST only.
Implements Master Prompt Phase 4 (build the signal detector) per
`BOT_B_DETECTOR_SPEC.md`.

## Added

- `backend/bot_b.py` — the detector layer over the existing, unmodified
  Strategy B evaluator:
  - `evaluate_bot_b(...)` — one pure evaluation returning the prompt
    section 4 explanation record and one of the five classifications.
  - Paper-trade record produced ONLY on VALIDATED PAPER SIGNAL — a
    simulated fill (data) for the Dashboard's PAPER journal. No network,
    no orders, no execution endpoint.
  - `BotBDetector` — audit trail (in-memory + optional JSONL append) with
    duplicate suppression keyed on classification + direction + bar time
    + range (event identity, same discipline as PR #21).
- `backend/tests/test_bot_b.py` — 20 tests covering the Master Prompt's
  eleven named cases plus the approval/parameter safety gates.
  Result: 20 passed; the existing engine suite still passes (59 total).

## Classification decisions recorded (Ambiguity Register A-6)

- Engulfing not yet confirmed at a boundary → CONFIRMATION PENDING (a
  stateless evaluation cannot call an unformed confirmation "failed";
  NO TRADE is reserved for affirmative failures).
- Timeframe/indicator conflict (evaluator Rule 4) → NO TRADE (the prompt:
  "Reject incomplete or contradictory confirmations").
- Stop beyond a SUPPLIED risk limit → NO TRADE; risk limit or exit
  conditions MISSING → CONFIRMATION PENDING with the parameter named.
- Rules pass but parameters unapproved → CONFIRMATION PENDING, never
  VALIDATED (evaluator state DISABLED_PENDING_PARAMETERS).
- POTENTIAL SETUP requires the evaluator's midpoint half plus the last
  close moving toward that boundary — no invented zone width.
- A supplied snapshot must carry a fresh timestamp (fail-closed, the
  PR #21 standard); stale/missing-timestamp data → NO TRADE.

## Not in this phase

- No changes to `strategy_engine.py`, `strategy_rules.py`, Strategy A,
  or `server.py`. No endpoints added; nothing deployed; no merge.
- Phase 5 historical testing is fixture-based (no MNQ bar archive exists
  in the repo); these 20 tests are its first suite. A recorded-dataset
  run remains open if a dataset is supplied.
- Phase 6 alerts and the live paper-trading test run on the migration
  target (Render) after the founder's secrets step and after he supplies
  the test parameters (range, risk limit, exit conditions) and approves
  the parameters flag for the test deployment.
