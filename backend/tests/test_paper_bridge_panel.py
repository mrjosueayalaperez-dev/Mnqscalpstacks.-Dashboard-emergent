"""Paper bridge dashboard panel — frontend-facing tests.

The panel (frontend/src/components/operator/PaperBridgePanel.js) is a
React component; this repo has no JS test runner wired into the
backend suites, so — in the established style of
tests/hardening/test_p0_item3_labels.py — these tests inspect the
panel source for the required sections and labeling rules, and pair
that with a live consistency check: every payload field the panel
consumes must exist in the REAL /api/paper-bridge/status response,
built from a real bridge journal (the acceptance suite's Harness —
the real pipeline, Analyst consumer, and Stage 2 engine; nothing
about the payload shape is hand-mocked).

Rules under test (paper-readiness mission, Stage 3 completion):
- The panel renders only the status endpoint's payload; with no
  payload it shows an explicit unavailable state, never figures.
- PAPER / SIMULATED labeling appears wherever positions or fills do.
- The Analyst provider label is rendered verbatim from the payload.
- The words LIVE, CONNECTED, EXECUTING, PROFITABLE never appear as
  status claims in the panel markup. (NOT_CONNECTED and
  PROVIDER_NOT_CONNECTED are the payload's truthful values — they are
  stripped before the scan, mirroring the acceptance test's
  forbidden-value check at the markup level.)
- Extended claim patterns (Zelator refinement, Nov 20 2026): blocking
  four bare words is necessary but not sufficient. Misleading
  equivalents and combinations — "live trading", "connected to the
  broker", "real-time execution", "orders are executing", "profit"
  claims — are banned by the documented pattern list below, applied
  to the panel markup AND to every string in the real status payload.
  "Connected" in any form trips the scan unless it is part of an
  explicit negation (NOT_CONNECTED / DISCONNECTED /
  PROVIDER_NOT_CONNECTED are required truthful labels here).
"""

import copy
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("MONGO_URL", "mongodb://localhost:1")  # never contacted

ROOT = Path(__file__).resolve().parents[2]
PANEL = ROOT / "frontend" / "src" / "components" / "operator" \
    / "PaperBridgePanel.js"
COCKPIT = ROOT / "frontend" / "src" / "components" / "operator" \
    / "OperatorCockpit.js"

LABEL = "DETERMINISTIC_FALLBACK — PROVIDER_NOT_CONNECTED"

REQUIRED_TESTIDS = (
    "paper-bridge-panel", "pb-pipeline", "pb-strategy-a", "pb-strategy-b",
    "pb-analyst", "pb-outcomes", "pb-position", "pb-history", "pb-risk",
    "pb-connectivity", "pb-unavailable",
)

# Every payload path the panel reads, as dotted keys. The consistency
# test resolves each one against the real endpoint response and checks
# each leaf key literally appears in the panel source, so this list
# cannot drift from what the panel actually consumes.
PANEL_PAYLOAD_PATHS = (
    "environment", "data_label",
    "pipeline.records_journaled", "pipeline.rejections_journaled",
    "pipeline.latest_qualified_signal_id",
    "strategies.STRATEGY_A", "strategies.STRATEGY_B",
    "analyst.provider_status", "analyst.explanation_source",
    "analyst.reviews_recorded",
    "paper.position", "paper.executions", "paper.fills_source",
    "paper.journal_entries",
    "risk.automation_paused", "risk.automated_entries",
    "risk.kill_switch", "risk.daily_pnl",
    "risk.daily_trades", "risk.max_daily_loss", "risk.max_daily_trades",
    "risk.paper_profile.qty", "risk.paper_profile.target_r",
    "risk.max_order_qty", "risk.max_bracket_ticks",
    "risk.risk_approval_status",
    "connectivity.provider", "connectivity.market_data",
)


def _panel_src():
    return PANEL.read_text()


def _load_acceptance():
    path = Path(__file__).with_name("test_paper_bridge_acceptance.py")
    spec = importlib.util.spec_from_file_location("pb_acceptance", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def harness(tmp_path):
    h = _load_acceptance().Harness(tmp_path)
    yield h
    h.close()


# ---------------------------------------------------------------------------
# Markup: sections and labeling
# ---------------------------------------------------------------------------

def test_panel_sections_and_sim_labeling():
    src = _panel_src()
    for testid in REQUIRED_TESTIDS:
        assert f'data-testid="{testid}"' in src, testid
    assert "/paper-bridge/status" in src
    # PAPER / SIMULATED labeling on the panel, its position section,
    # and its fill history.
    assert "SIMULATED FILLS ONLY" in src
    assert "Paper Position" in src and "SIM" in src
    assert "Simulated Order / Fill History" in src
    # Per-strategy sections for both independent strategies.
    assert "Strategy A" in src and "Strategy B" in src
    # Risk state surfaces the approval status and the paused state.
    assert "risk_approval_status" in src
    assert "PAUSED" in src


def test_panel_forbidden_words_absent():
    src = _panel_src()
    # The payload's truthful values are not status claims; strip them
    # before scanning, exactly as the acceptance test excludes the
    # quoted-value forms from the JSON payload.
    stripped = src.replace("PROVIDER_NOT_CONNECTED", "") \
                  .replace("NOT_CONNECTED", "")
    for word in ("LIVE", "CONNECTED", "EXECUTING", "PROFITABLE"):
        hits = re.findall(rf"\b{word}\b", stripped, flags=re.IGNORECASE)
        assert not hits, (word, hits)


# ---------------------------------------------------------------------------
# Extended forbidden-claim patterns (Zelator refinement, Nov 20 2026)
#
# The four-word scan above catches bare status words. It does NOT catch
# claim-shaped phrases, which are how a surface actually misleads:
# nobody writes the bare word LIVE as a claim — they write "live
# trading". Each pattern below is a distinct claim shape, with its
# rationale. Overlap between patterns is deliberate defense-in-depth:
# a phrase must survive EVERY pattern, not just one.
#
# Negation rule (segment-level evaluation — Zelator negation
# challenge, Nov 20 2026): the COMPLETE claim is evaluated; nothing
# is stripped. The text is split into clause-sized segments on
# sentence/clause delimiters, and a segment is exempt ONLY when it
# consists of exactly one documented truthful negation clause
# (trimmed, case-insensitive): the labels NOT_CONNECTED /
# PROVIDER_NOT_CONNECTED / DISCONNECTED standing alone, or the
# backend market_data clause "no live feed is read by this bridge"
# standing alone as a complete clause. Every other segment is
# scanned UNSTRIPPED, so a label glued to claim text with a space
# ("NOT_CONNECTED to broker"), fused into one token
# ("NOT_CONNECTED_AND_LIVE"), or placed beside a claim in the same
# string is evaluated whole — and trips. This replaces the earlier
# strip-negations-first design, which masked exactly those cases:
# stripping deleted the only "connected" in "NOT_CONNECTED to
# broker" and reduced "NOT_CONNECTED_AND_LIVE" to "_AND_LIVE",
# which \blive\b cannot match ("_" is a word character). The
# backend's "no live feed is read..." sentence still passes —
# honestly, by clause-level evaluation: its negation clause is a
# complete truthful statement standing alone between delimiters,
# and the clauses around it ("LOCAL_ONLY", "the tape is set from
# signal records and supplied prices") scan clean on their own.
# Delimiters deliberately exclude "-" and "_": hyphen-splitting
# would break the "real-time execution" pattern, and underscore-
# splitting would resurrect the fused-token masking hole.
# ---------------------------------------------------------------------------

_SEGMENT_SPLIT_RE = re.compile(r"[.!?;:\n\r—–·|()\[\]]+")

_EXEMPT_SEGMENTS = frozenset({
    "provider_not_connected",
    "not_connected",
    "disconnected",
    # The backend payload's market_data negation clause, verbatim
    # (paper_bridge.py) — exempt only as a complete clause.
    "no live feed is read by this bridge",
})


def _segment_exempt(segment):
    return segment.strip().casefold() in _EXEMPT_SEGMENTS


FORBIDDEN_CLAIM_PATTERNS = (
    # -- "live" family -------------------------------------------------
    (
        "live-word",
        r"\blive\b",
        "Any standalone use of the word 'live' as a descriptor. This "
        "surface reads recorded journal state and local fixtures only; "
        "it has no truthful sentence that needs the word. The bare-word "
        "scan already bans the quoted status value; this extends the "
        "ban to every prose use in the panel's own copy.",
    ),
    (
        "live-trading",
        r"live[-\s]trading|trading[-\s](is[-\s])?live",
        "'Live trading' / 'trading live' — the canonical misleading "
        "combination: it claims real-market execution is happening. "
        "Named explicitly because it is the phrase a reader actually "
        "encounters; defense-in-depth alongside live-word.",
    ),
    (
        "live-market-data",
        r"live[-\s](market|feed|data|prices?|quotes?)\b",
        "'Live market / feed / data / prices' claims a streaming "
        "market connection this bridge does not have (its tape is set "
        "from signal records). The payload's negation clause about "
        "the absent feed is exempt only as a complete clause (see "
        "the negation rule above), never as a substring strip.",
    ),
    (
        "go-live",
        r"go[-\s]live|now[-\s]live|went[-\s]live",
        "'Go live / now live' announces activation of a real system — "
        "a deployment claim, not a status this local surface can make.",
    ),
    # -- "connected" family --------------------------------------------
    (
        "connected-unnegated",
        r"connected",
        "'Connected' in ANY form (connected, reconnected, "
        "interconnected...) that is not a complete negation clause "
        "standing alone. Implemented as a substring scan over every "
        "non-exempt segment (see the negation rule above): a label "
        "that IS the whole segment is exempt, but a segment holding "
        "a label plus anything else is scanned whole, so even the "
        "'connected' inside a glued NOT_CONNECTED trips. A provider "
        "registry entry or a rendered NOT_CONNECTED value is not a "
        "connection; no affirmative form of the word is truthful "
        "here.",
    ),
    (
        "connected-to-venue",
        r"connected\s+to\s+(the\s+)?(broker|exchange|market|feed|server|venue)",
        "'Connected to the broker/exchange/market/...' — the specific "
        "venue-connection claim, named because it is the most "
        "consequential false statement this panel could make. Also "
        "caught by connected-unnegated; listed for the record.",
    ),
    # -- execution-activity family --------------------------------------
    (
        "executing-present-tense",
        r"\bexecuting\b",
        "Present-tense 'executing' claims orders are being executed "
        "right now. This bridge writes simulated journal entries "
        "through a local engine; nothing is executing anywhere. (The "
        "past-tense record status EXECUTED is data, not an activity "
        "claim, and is not matched.)",
    ),
    (
        "execution-active",
        r"execution\s+(is\s+)?active|active\s+execution|orders?\s+(are\s+|is\s+)?executing|execution\s+in\s+progress",
        "'Execution active', 'orders are executing', 'execution in "
        "progress' — activity claims in combination form, which the "
        "bare-word scan cannot see. The noun 'execution(s)' alone "
        "(execution records, bridge executions) is a truthful record "
        "label and is deliberately NOT banned.",
    ),
    (
        "realtime-execution",
        r"real[-\s]?time\s+execution",
        "'Real-time execution' combines a latency claim with an "
        "execution claim; both halves are false for this surface.",
    ),
    # -- profit family ---------------------------------------------------
    (
        "profit-word",
        r"\bprofit\w*\b",
        "'Profit' in any form (profit, profitable, profits). Zelator's "
        "rule bans it in a status context; this panel applies the "
        "stricter panel-wide ban deliberately: the only money figures "
        "here are simulated PnL values, labeled 'PnL (SIM)', and no "
        "truthful copy on this surface needs the word. A 'profit' "
        "claim would imply earned returns from a paper journal.",
    ),
)


def _claim_hits(text):
    """All (pattern-name, match) forbidden-claim hits in `text`.

    The complete claim is evaluated: the text is split into
    clause-sized segments; a segment consisting of exactly one
    documented truthful negation clause is exempt; every other
    segment is scanned unstripped against every pattern.
    """
    hits = []
    for segment in _SEGMENT_SPLIT_RE.split(text):
        if _segment_exempt(segment):
            continue
        for name, pattern, _why in FORBIDDEN_CLAIM_PATTERNS:
            for m in re.finditer(pattern, segment, flags=re.IGNORECASE):
                hits.append((name, m.group(0)))
    return hits


def _all_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for value in node.values():
            yield from _all_strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _all_strings(value)


def test_panel_forbidden_claim_patterns():
    hits = _claim_hits(_panel_src())
    assert not hits, hits


def test_panel_unavailable_state_is_explicit_and_first():
    src = _panel_src()
    # No payload -> explicit unavailable state, rendered before any
    # data section (an early return on the null state), so an
    # unreachable endpoint can never surface as zeros dressed as data.
    assert "useState(null)" in src
    assert "if (!status)" in src
    assert "STATUS UNAVAILABLE" in src
    assert src.index("STATUS UNAVAILABLE") < src.index("pb-pipeline")
    assert "No figures are shown" in src
    # The panel's only state is the payload itself — no numeric or
    # object initial state that could masquerade as data.
    assert "useState(0)" not in src
    assert "useState({" not in src


def test_cockpit_mounts_panel():
    src = COCKPIT.read_text()
    assert 'import PaperBridgePanel from "./PaperBridgePanel"' in src
    assert "<PaperBridgePanel" in src


# ---------------------------------------------------------------------------
# Consistency: panel contract vs the real endpoint payload
# ---------------------------------------------------------------------------

def _resolve(body, dotted):
    node = body
    for part in dotted.split("."):
        assert isinstance(node, dict) and part in node, dotted
        node = node[part]
    return node


def test_panel_payload_contract_matches_real_response(harness, monkeypatch):
    import paper_bridge_api
    from fastapi.testclient import TestClient
    import server

    # Real journal state: one qualified B record executed end-to-end.
    out = harness.b_record()
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(out["record"])
    assert res["status"] == "EXECUTED"
    monkeypatch.setattr(paper_bridge_api, "_bridge", harness.bridge)

    client = TestClient(server.app)
    resp = client.get("/api/paper-bridge/status")
    assert resp.status_code == 200
    body = resp.json()

    src = _panel_src()
    for dotted in PANEL_PAYLOAD_PATHS:
        _resolve(body, dotted)
        leaf = dotted.rsplit(".", 1)[-1]
        assert leaf in src, (dotted, leaf)

    # The values the panel renders verbatim are the truthful ones.
    assert body["environment"] == "PAPER"
    assert body["analyst"]["explanation_source"] == LABEL
    assert body["analyst"]["provider_status"] == "NOT_CONNECTED"
    assert body["connectivity"]["provider"] == "NOT_CONNECTED"
    assert body["risk"]["risk_approval_status"] == "UNAPPROVED"
    assert body["paper"]["fills_source"] == "SIMULATED"

    # Execution-record and position fields the panel renders all exist
    # on the real records.
    assert len(body["paper"]["executions"]) == 1
    execution = body["paper"]["executions"][0]
    for key in ("signal_id", "strategy_id", "status", "reason", "order"):
        assert key in execution, key
        assert key in src, key
    for key in ("fill_price", "fill_price_source", "sl_price",
                "tp_price", "qty"):
        assert key in execution["order"], key
        assert key in src, key
    assert execution["order"]["fill_price_source"] == "SIMULATED"
    position = body["paper"]["position"]
    for key in ("side", "qty", "avg_entry", "sl_price", "tp_price",
                "unrealized_pnl"):
        assert key in position, key
        assert key in src, key

    # The payload behind the panel carries no forbidden status claims
    # either (same quoted-value rule as the acceptance test).
    blob = json.dumps(body)
    for forbidden in ('"LIVE"', '"EXECUTING"', '"PROFITABLE"',
                      '"CONNECTED"'):
        assert forbidden not in blob


def test_status_payload_has_no_forbidden_claims(harness, monkeypatch):
    # The extended claim patterns apply to what the panel actually
    # renders, not just to its source: every human-readable string in
    # the real payload (labels, reasons, the market-data sentence, the
    # Analyst explanation source) must survive the same scan, with the
    # payload's explicit negations (NOT_CONNECTED,
    # PROVIDER_NOT_CONNECTED, "no live feed is read...") stripped as
    # truthful labels, not claims.
    import paper_bridge_api
    from fastapi.testclient import TestClient
    import server

    out = harness.b_record()
    harness.bridge.set_automation_paused(False)
    res = harness.bridge.execute_record(out["record"])
    assert res["status"] == "EXECUTED"
    monkeypatch.setattr(paper_bridge_api, "_bridge", harness.bridge)

    client = TestClient(server.app)
    body = client.get("/api/paper-bridge/status").json()

    hits = []
    for value in _all_strings(body):
        for name, match in _claim_hits(value):
            hits.append((name, match, value))
    assert not hits, hits


# ---------------------------------------------------------------------------
# Adversarial negation cases (Zelator negation challenge, Nov 20 2026)
#
# The strip-negations-first scanner had a masking hole: it deleted the
# negation labels as substrings BEFORE evaluating the claim, so a
# claim glued to a label could be destroyed by the strip itself.
# Measured against the strip-first implementation (Nov 20, before the
# segment redesign): "NOT_CONNECTED to broker" and
# "NOT_CONNECTED_AND_LIVE" SLIPPED (zero hits) — the first lost its
# only "connected" to the strip; the second was reduced to "_AND_LIVE",
# which \blive\b cannot match because "_" is a word character. The
# other six cases below tripped. The scanner now evaluates the
# COMPLETE claim (see the negation rule above _claim_hits): a negation
# label exempts only a segment consisting of exactly that label, and
# every other segment is scanned unstripped, so a label can never hide
# a claim glued to it, wrapped around it, or placed after it.
# ---------------------------------------------------------------------------

ADVERSARIAL_NEGATION_STRINGS = (
    # Zelator's named case: safe label, then the contradictory claim.
    "NOT_CONNECTED — now connected to broker",
    # Label glued to the claim with only a space (strip-first SLIP).
    "NOT_CONNECTED to broker",
    # Label as a prefix, claim after the colon.
    "PROVIDER_NOT_CONNECTED: live trading enabled",
    # Negation in the past tense, affirmative claim after the dash.
    "DISCONNECTED — reconnected to exchange",
    # Claim in a parenthesis beside the label.
    "Status: NOT_CONNECTED (connected to market data)",
    # Label and claim fused into one token (strip-first SLIP).
    "NOT_CONNECTED_AND_LIVE",
    # Claim BEFORE the label — order must not matter.
    "connected to broker — NOT_CONNECTED",
)


@pytest.mark.parametrize("text", ADVERSARIAL_NEGATION_STRINGS)
def test_adversarial_negation_glued_claims_rejected(text):
    hits = _claim_hits(text)
    assert hits, text


def test_adversarial_payload_claim_in_sibling_field_rejected():
    # The payload scan is per-string: a truthful label in one field
    # must never launder a claim sitting in another field of the same
    # payload.
    payload = {"provider": "NOT_CONNECTED",
               "note": "live trading enabled"}
    hits = []
    for value in _all_strings(payload):
        for name, match in _claim_hits(value):
            hits.append((name, match, value))
    assert hits, payload


TRUTHFUL_NEGATION_STRINGS = (
    # The three required negation labels, each standing alone.
    "NOT_CONNECTED",
    "PROVIDER_NOT_CONNECTED",
    "DISCONNECTED",
    # The Analyst explanation-source label, rendered verbatim.
    LABEL,
    # The backend's market_data sentence: a complete truthful
    # negation statement ("no live feed is read...") — it passes by
    # sentence-level evaluation, not by stripping the word "live".
    "LOCAL_ONLY — no live feed is read by this bridge; the tape is "
    "set from signal records and supplied prices",
    # The panel's own status banner.
    "PAPER · SIMULATED FILLS ONLY · UNAPPROVED",
    # The noun "executions" as a record label is not an activity
    # claim (documented under FORBIDDEN_CLAIM_PATTERNS).
    "Execution records: 3",
)


@pytest.mark.parametrize("text", TRUTHFUL_NEGATION_STRINGS)
def test_truthful_negation_strings_still_pass(text):
    hits = _claim_hits(text)
    assert not hits, (text, hits)


# ---------------------------------------------------------------------------
# Batch 1 (Nov 21, 2026): PV-06 contradiction validation + PV-07 pin
#
# PV-06: truthful labels alone do not protect an operator if the
# payload's fields contradict EACH OTHER. The panel now runs the pure
# validator (frontend/src/components/operator/
# paperBridgeStatusValidation.js — rules V-01…V-09 + V-11 from the
# correction package §4a; V-10 is an explicit non-rule) before
# rendering, and fails closed on a contradictory payload.
#
# PV-07: the anti-staleness behavior (the refresh() catch dropping
# the held payload) was present but unpinned — every pre-Batch-1 test
# would have passed with that line removed. It is pinned below.
# ---------------------------------------------------------------------------

VALIDATOR = ROOT / "frontend" / "src" / "components" / "operator" \
    / "paperBridgeStatusValidation.js"

_NODE_DRIVER = """
const fs = require("fs");
const { validatePaperBridgeStatus } = require(process.argv[2]);
const cases = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const out = cases.map((c) => {
  const v = validatePaperBridgeStatus(c.payload);
  return { name: c.name, classification: v.classification,
           rules: v.violations.map((x) => x.rule) };
});
console.log(JSON.stringify(out));
"""


def _run_validator(cases, tmp_path):
    """Execute the SHIPPED validator under Node over `cases`
    ([{name, payload}]) and return {name: (classification, [rules])}.

    Fail-closed environment rule (correction package §4d): if Node
    is unavailable this FAILS, never skips — a silently skipped
    validator test would recreate exactly the PV-07 hole this batch
    exists to close.
    """
    node = shutil.which("node")
    if node is None:
        pytest.fail(
            "Node is required to execute the shipped paper-bridge "
            "status validator; without it the PV-06 truth table "
            "cannot run, and this test fails rather than skips.")
    driver = tmp_path / "validator_driver.js"
    driver.write_text(_NODE_DRIVER)
    cases_file = tmp_path / "validator_cases.json"
    cases_file.write_text(json.dumps(cases))
    proc = subprocess.run(
        [node, str(driver), str(VALIDATOR), str(cases_file)],
        capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return {row["name"]: (row["classification"], row["rules"])
            for row in json.loads(proc.stdout)}


def _json_roundtrip(payload):
    return json.loads(json.dumps(payload))


def test_validator_truth_table_over_real_payloads(tmp_path):
    acc = _load_acceptance()
    cases = []

    # -- Valid combinations, all built from real bridge journals ----
    h = acc.Harness(tmp_path / "executed")
    out = h.b_record()
    h.bridge.set_automation_paused(False)
    res = h.bridge.execute_record(out["record"])
    assert res["status"] == "EXECUTED"
    p_exec = _json_roundtrip(h.bridge.status())
    cases.append({"name": "fresh-executed", "payload": p_exec})

    # V-10 valid combination (explicit non-rule): automation paused
    # NOW, alongside EXECUTED history. Pause is current state, the
    # outcome is history — the validator must NOT flag it.
    h.bridge.set_automation_paused(True)
    cases.append({"name": "fresh-v10-paused-with-history",
                  "payload": _json_roundtrip(h.bridge.status())})
    h.close()

    # EXECUTED_JOURNAL_FAILED shape: a real executed payload whose
    # risk outcome carries the journal-failed label. The deliberate
    # non-rule applies — no journal_entries >= executions identity
    # may be asserted, because that outcome exists precisely for
    # journaling failing after execution. (Constructed by relabeling
    # the outcome on a copy of the real payload; the shape — every
    # key — is the builder's own.)
    p_jf = copy.deepcopy(p_exec)
    order = p_jf["paper"]["executions"][0]["order"]
    order["bridge"]["risk_decision"]["outcome"] = \
        "EXECUTED_JOURNAL_FAILED"
    cases.append({"name": "fresh-journal-failed-shape",
                  "payload": p_jf})

    # V-06 divergent-order combination: two B records rejected while
    # paused; after resume the FIRST is re-presented and executes.
    # The builder orders the strategies projection by updated_ts and
    # the executions list by created_ts, so the projection names the
    # re-presented record while the array's last B row is the second
    # record. Same-row coherence (the relation the builder actually
    # guarantees) must classify this fresh; an array-order reading
    # would manufacture a false invalid out of the bridge's own
    # documented re-presentation flow.
    h = acc.Harness(tmp_path / "divergent")
    rec1 = h.b_record()["record"]
    rec2 = copy.deepcopy(rec1)
    rec2["signal_id"] = rec1["signal_id"] + "-second"
    assert h.bridge.execute_record(rec1)["status"] == "REJECTED"
    assert h.bridge.execute_record(rec2)["status"] == "REJECTED"
    h.bridge.set_automation_paused(False)
    h.reset_cooldown()
    assert h.bridge.execute_record(rec1)["status"] == "EXECUTED"
    p_div = _json_roundtrip(h.bridge.status())
    b_rows = [e for e in p_div["paper"]["executions"]
              if e["strategy_id"] == "STRATEGY_B"]
    # Pin the precondition: this case IS divergent, and cannot
    # silently degenerate into an array-ordered one.
    assert p_div["strategies"]["STRATEGY_B"]["last_signal_id"] \
        == rec1["signal_id"]
    assert b_rows[-1]["signal_id"] == rec2["signal_id"]
    assert b_rows[-1]["status"] != \
        p_div["strategies"]["STRATEGY_B"]["last_outcome"]
    cases.append({"name": "fresh-v06-divergent-order",
                  "payload": p_div})
    h.close()

    # Empty bridge: no executions, flat position, counts at zero.
    h = acc.Harness(tmp_path / "empty")
    cases.append({"name": "fresh-empty",
                  "payload": _json_roundtrip(h.bridge.status())})
    h.close()

    # No payload at all -> UNAVAILABLE.
    cases.append({"name": "unavailable-null", "payload": None})

    # -- One mutation per rule, each on a copy of the real payload --
    def mut(name, fn):
        p = copy.deepcopy(p_exec)
        fn(p)
        cases.append({"name": name, "payload": p})

    mut("viol-v01", lambda p: p.update(environment="NOT_PAPER"))
    mut("viol-v02", lambda p: p["analyst"].update(
        provider_status="CONNECTED"))
    mut("viol-v03", lambda p: p["risk"].update(
        risk_approval_status="APPROVED"))
    mut("viol-v04", lambda p: p["pipeline"].update(
        records_journaled=None))
    mut("viol-v05-negative", lambda p: p["pipeline"].update(
        records_journaled=-1))
    mut("viol-v05-latest-on-empty", lambda p: p["pipeline"].update(
        records_journaled=0))
    mut("viol-v06", lambda p: p["strategies"]["STRATEGY_B"].update(
        last_outcome="REJECTED"))
    mut("viol-v07", lambda p: p["analyst"].update(
        reviews_recorded=len(p["paper"]["executions"]) + 1))
    mut("viol-v08", lambda p: p["paper"].update(position={
        "side": None, "qty": 0, "avg_entry": 0.0, "sl_price": None,
        "tp_price": None, "unrealized_pnl": 0.0}))
    mut("viol-v09", lambda p: p["paper"].update(
        fills_source="BROKER"))
    mut("viol-v11", lambda p: p.pop("risk"))

    results = _run_validator(cases, tmp_path)

    for name in ("fresh-executed", "fresh-v10-paused-with-history",
                 "fresh-journal-failed-shape",
                 "fresh-v06-divergent-order", "fresh-empty"):
        classification, rules = results[name]
        assert classification == "fresh", (name, rules)
        assert rules == [], (name, rules)
    assert results["unavailable-null"] == ("unavailable", [])

    expected = {
        "viol-v01": "V-01", "viol-v02": "V-02", "viol-v03": "V-03",
        "viol-v04": "V-04", "viol-v05-negative": "V-05",
        "viol-v05-latest-on-empty": "V-05", "viol-v06": "V-06",
        "viol-v07": "V-07", "viol-v08": "V-08", "viol-v09": "V-09",
        "viol-v11": "V-11",
    }
    for name, rule in expected.items():
        classification, rules = results[name]
        assert classification == "contradictory", (name, rules)
        # Isolation: the mutation trips exactly its own rule.
        assert rules == [rule], (name, rules)


# ---------------------------------------------------------------------------
# PV-07 pin — the anti-staleness line, pinned at source level.
#
# Why source-level: this repo has no JS test runner (see this file's
# header), so a behavioral fetch-failure component test is not
# feasible today; the structural assertion below is the strongest
# pin the established setup supports, and it is brittle in the right
# direction — renaming or removing the line fails loudly. If a JS
# runner is ever adopted, a behavioral test (failed refresh after a
# successful one -> unavailable state, no stale figures) is the
# required replacement for this pin.
# ---------------------------------------------------------------------------

_CATCH_RE = re.compile(r"catch \(e\) \{(?P<body>.*?)\n    \}",
                       re.DOTALL)


def _catch_block_clears_state(src):
    """True iff refresh()'s catch block drops the held payload —
    the line that makes stale-after-failure impossible by design."""
    m = _CATCH_RE.search(src)
    return bool(m) and "setStatus(null)" in m.group("body")


def test_pv07_pin_catch_block_clears_state():
    assert _catch_block_clears_state(_panel_src())


def test_pv07_pin_rejects_mutated_source():
    # Mutation check, in-suite: with the state-clearing line removed
    # from a copy of the source, the pin must fail. (The tree itself
    # is never mutated.)
    src = _panel_src()
    assert _catch_block_clears_state(src)  # control: pin holds
    mutated = src.replace("      setStatus(null);\n", "", 1)
    assert mutated != src
    assert not _catch_block_clears_state(mutated)


# ---------------------------------------------------------------------------
# Batch 1 wiring assertions — validator wired in, INVALID state
# fail-closed, diagnostics from the validator's output only.
# ---------------------------------------------------------------------------

def test_panel_wiring_validator_and_invalid_state():
    src = _panel_src()
    assert 'from "./paperBridgeStatusValidation"' in src
    assert "validatePaperBridgeStatus(data)" in src
    # Validation happens on fetch, before the payload is stored for
    # rendering.
    assert src.index("validatePaperBridgeStatus(data)") \
        < src.index("setStatus(data)")
    # The INVALID state's copy (also covered by the claims scanner
    # above, which scans the whole panel source).
    assert "STATUS INVALID — INCONSISTENT PAYLOAD" in src
    # (Whitespace-normalized: the sentence wraps across JSX lines.)
    assert "No figures are shown, because none can be trusted" \
        in " ".join(src.split())
    assert 'data-testid="pb-invalid"' in src
    # Diagnostics render from the validator's output.
    assert "validation.violations.map" in src
    # The INVALID branch renders no status section and dereferences
    # no payload section — the contradictory figures cannot leak
    # into it, in whole or in part.
    start = src.index('validation.classification === "contradictory"')
    end = src.index("const pipeline = status.pipeline")
    block = src[start:end]
    for testid in ("pb-pipeline", "pb-strategy-a", "pb-strategy-b",
                   "pb-analyst", "pb-outcomes", "pb-position",
                   "pb-history", "pb-risk", "pb-connectivity"):
        assert f'data-testid="{testid}"' not in block, testid
    for deref in ("status.pipeline", "status.strategies",
                  "status.analyst", "status.paper", "status.risk",
                  "status.connectivity"):
        assert deref not in block, deref
