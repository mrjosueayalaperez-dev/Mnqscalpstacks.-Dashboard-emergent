// Paper bridge status validation — PV-06 correction (Batch 1, Nov 21
// 2026). A pure, dependency-free pre-render check on the
// GET /api/paper-bridge/status payload, implementing the valid-
// combination matrix from the correction package §4a (rules V-01…V-09
// and V-11; V-10 is an explicit non-rule, documented below).
//
// Why this exists: the panel renders whatever the endpoint returns.
// Truthful labels alone do not protect an operator if the payload's
// fields contradict EACH OTHER (a position with no execution behind
// it, a projection that disagrees with the execution list, counts
// that silently nulled). This validator classifies every payload
// before the panel renders it:
//
//   "unavailable"   — no payload (null/absent). The panel's existing
//                     unavailable state covers this; the validator
//                     merely names it so the panel has one call site.
//   "fresh"         — payload received this fetch cycle AND every
//                     rule holds. Rendered exactly as before.
//   "contradictory" — payload received AND at least one rule is
//                     violated. The panel fails closed: an explicit
//                     INVALID state, no figures rendered as status,
//                     violations preserved as diagnostic evidence.
//
// There is deliberately NO "stale" classification: stale cannot
// occur by design, because the panel drops the prior payload on any
// fetch failure (PaperBridgePanel.js, the refresh() catch — pinned
// by the PV-07 test in backend/tests/test_paper_bridge_panel.py)
// instead of retaining it. If a future design ever retains data
// across a failed refresh, it must add the fourth state here
// (retained data, visibly marked with its last-successful-update
// time) before that design ships.
//
// Purity contract: no imports, no I/O, no Date, no Math.random — the
// same input always yields the same verdict, so the repo's Python
// suite can execute this exact shipped function under Node (see the
// dual export at the bottom) instead of testing a reimplementation.
//
// Rule-guard convention: a rule is only evaluated when the fields it
// reads are present and of the types it expects; missing or mistyped
// structure is reported once, by V-11, and the dependent rules skip
// rather than piling on secondary violations.

const EXPECTED_SURFACE = "paper_bridge_status";
const EXPECTED_ENVIRONMENT = "PAPER";
const EXPECTED_DATA_LABEL = "PAPER";
const EXPECTED_NOT_CONNECTED = "NOT_CONNECTED";
// The Analyst explanation-source label, verbatim from the backend
// (signal_contract.py EXPLANATION_SOURCE_FALLBACK): the words
// DETERMINISTIC_FALLBACK and PROVIDER_NOT_CONNECTED joined by an
// em dash (U+2014) with spaces.
const EXPECTED_EXPLANATION_SOURCE =
  "DETERMINISTIC_FALLBACK \u2014 PROVIDER_NOT_CONNECTED";
const EXPECTED_RISK_APPROVAL = "UNAPPROVED";
const EXPECTED_FILLS_SOURCE = "SIMULATED";
const STRATEGIES = ["STRATEGY_A", "STRATEGY_B"];

function isObj(v) {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function isInt(v) {
  return typeof v === "number" && Number.isInteger(v);
}

function isNum(v) {
  return typeof v === "number" && Number.isFinite(v);
}

function show(v) {
  if (v === undefined) return "undefined";
  const s = JSON.stringify(v);
  if (s === undefined) return String(v);
  return s.length > 120 ? s.slice(0, 117) + "..." : s;
}

function validatePaperBridgeStatus(payload) {
  if (payload === null || payload === undefined) {
    return { classification: "unavailable", violations: [] };
  }

  const violations = [];
  const add = (rule, field, expected, actual) =>
    violations.push({ rule, field, expected, actual: show(actual) });

  if (!isObj(payload)) {
    add("V-11", "(payload)", "a status object", payload);
    return { classification: "contradictory", violations };
  }

  // ---- V-11: structure — every top-level section present, typed ---
  // The vestigial pipeline.latest_signal_id key is explicitly
  // ignored (the builder always emits it as null), so a future
  // builder cleanup cannot false-trip this validator.
  const sectionTypes = [
    ["surface", "string"],
    ["environment", "string"],
    ["data_label", "string"],
    ["pipeline", "object"],
    ["strategies", "object"],
    ["analyst", "object"],
    ["paper", "object"],
    ["risk", "object"],
    ["connectivity", "object"],
  ];
  for (const [key, kind] of sectionTypes) {
    const v = payload[key];
    const ok = kind === "string" ? typeof v === "string" : isObj(v);
    if (!ok) add("V-11", key, kind + " section", v);
  }
  const pipeline = isObj(payload.pipeline) ? payload.pipeline : null;
  const strategies = isObj(payload.strategies) ? payload.strategies : null;
  const analyst = isObj(payload.analyst) ? payload.analyst : null;
  const paper = isObj(payload.paper) ? payload.paper : null;
  const risk = isObj(payload.risk) ? payload.risk : null;
  const connectivity = isObj(payload.connectivity)
    ? payload.connectivity
    : null;

  let position = null;
  let executions = null;
  if (paper) {
    if (!isObj(paper.position)) {
      add("V-11", "paper.position", "object", paper.position);
    } else {
      position = paper.position;
    }
    if (!Array.isArray(paper.executions)) {
      add("V-11", "paper.executions", "array", paper.executions);
    } else {
      executions = paper.executions;
    }
  }
  let profile = null;
  if (risk) {
    if (!isObj(risk.paper_profile)) {
      add("V-11", "risk.paper_profile", "object", risk.paper_profile);
    } else {
      profile = risk.paper_profile;
    }
  }
  if (strategies) {
    for (const s of STRATEGIES) {
      if (!(s in strategies)) {
        add("V-11", "strategies." + s, "null or object", undefined);
      } else if (strategies[s] !== null && !isObj(strategies[s])) {
        add("V-11", "strategies." + s, "null or object", strategies[s]);
      }
    }
  }

  // ---- V-01: surface identity --------------------------------------
  if (typeof payload.surface === "string" &&
      payload.surface !== EXPECTED_SURFACE) {
    add("V-01", "surface", show(EXPECTED_SURFACE), payload.surface);
  }
  if (typeof payload.environment === "string" &&
      payload.environment !== EXPECTED_ENVIRONMENT) {
    add("V-01", "environment", show(EXPECTED_ENVIRONMENT),
        payload.environment);
  }
  if (typeof payload.data_label === "string" &&
      payload.data_label !== EXPECTED_DATA_LABEL) {
    add("V-01", "data_label", show(EXPECTED_DATA_LABEL),
        payload.data_label);
  }

  // ---- V-02: provider state — this bridge has no provider path ----
  // Any value other than the verbatim not-connected state claims a
  // connection that cannot exist.
  if (analyst && typeof analyst.provider_status === "string" &&
      analyst.provider_status !== EXPECTED_NOT_CONNECTED) {
    add("V-02", "analyst.provider_status",
        show(EXPECTED_NOT_CONNECTED), analyst.provider_status);
  }
  if (connectivity && typeof connectivity.provider === "string" &&
      connectivity.provider !== EXPECTED_NOT_CONNECTED) {
    add("V-02", "connectivity.provider",
        show(EXPECTED_NOT_CONNECTED), connectivity.provider);
  }
  if (analyst && typeof analyst.explanation_source === "string" &&
      analyst.explanation_source !== EXPECTED_EXPLANATION_SOURCE) {
    add("V-02", "analyst.explanation_source",
        show(EXPECTED_EXPLANATION_SOURCE), analyst.explanation_source);
  }

  // ---- V-03: risk approval state and paper profile -----------------
  if (risk && typeof risk.risk_approval_status === "string" &&
      risk.risk_approval_status !== EXPECTED_RISK_APPROVAL) {
    add("V-03", "risk.risk_approval_status",
        show(EXPECTED_RISK_APPROVAL), risk.risk_approval_status);
  }
  if (profile) {
    if (!(isNum(profile.qty) && profile.qty > 0)) {
      add("V-03", "risk.paper_profile.qty", "a positive number",
          profile.qty);
    }
    if (!(isNum(profile.target_r) && profile.target_r > 0)) {
      add("V-03", "risk.paper_profile.target_r", "a positive number",
          profile.target_r);
    }
  }

  // ---- V-04 / V-05: pipeline counts --------------------------------
  // The builder initializes both counts to null, fills them on
  // success, or sets pipeline.error on failure. So: error present
  // requires both counts null; no error requires both counts
  // present. A null that reaches the client without error is a
  // builder regression dressed as zero.
  if (pipeline) {
    const hasError =
      pipeline.error !== undefined && pipeline.error !== null;
    const countFields = ["records_journaled", "rejections_journaled"];
    for (const f of countFields) {
      const v = pipeline[f];
      if (hasError && v !== null && v !== undefined) {
        add("V-04", "pipeline." + f,
            "null while pipeline.error is present", v);
      }
      if (!hasError && (v === null || v === undefined)) {
        add("V-04", "pipeline." + f,
            "an integer count (no pipeline.error explains a null)", v);
      }
      if (v !== null && v !== undefined && !(isInt(v) && v >= 0)) {
        add("V-05", "pipeline." + f, "an integer >= 0", v);
      }
    }
    // A qualified signal cannot exist in an empty records journal.
    const latest = pipeline.latest_qualified_signal_id;
    if (isObj(latest) && pipeline.records_journaled === 0) {
      for (const s of STRATEGIES) {
        if (latest[s] !== null && latest[s] !== undefined) {
          add("V-05", "pipeline.latest_qualified_signal_id." + s,
              "null while records_journaled is 0", latest[s]);
        }
      }
    }
  }

  // ---- V-06: per-strategy projection coherence ---------------------
  // The strategies projection and the executions list are two reads
  // of the same bridge_executions rows in one builder call. The
  // relation the builder guarantees — and the one checked here — is
  // same-row coherence: the projection for a strategy is null exactly
  // when no execution exists for it, and when non-null it names a
  // real execution of that strategy and reports that execution's
  // status faithfully.
  //
  // Deliberately NOT asserted: that the named execution is the last
  // one in the executions array. The builder orders the projection
  // by updated_ts and the list by created_ts, and the payload
  // carries no per-execution timestamps, so array order is not the
  // builder's guarantee (a record re-presented after a state-
  // dependent rejection, or an exit journaled after a later
  // rejection, legitimately reorders the two). Asserting array order
  // would manufacture false invalids out of the bridge's own
  // documented flows; the correction package's V-06 intent —
  // disagreement means the payload was assembled outside the
  // builder — is fully served by same-row coherence.
  if (strategies && executions) {
    for (const s of STRATEGIES) {
      if (!(s in strategies)) continue;
      const info = strategies[s];
      if (info !== null && !isObj(info)) continue; // V-11 owns it
      const rows = executions.filter(
        (e) => isObj(e) && e.strategy_id === s
      );
      if (info === null) {
        if (rows.length > 0) {
          add("V-06", "strategies." + s,
              "non-null (executions exist for this strategy)", null);
        }
        continue;
      }
      if (rows.length === 0) {
        add("V-06", "strategies." + s,
            "null (no executions for this strategy)", info);
        continue;
      }
      const named = rows.find((e) => e.signal_id === info.last_signal_id);
      if (!named) {
        add("V-06", "strategies." + s + ".last_signal_id",
            "the signal_id of an execution of this strategy",
            info.last_signal_id);
      } else if (named.status !== info.last_outcome) {
        add("V-06", "strategies." + s + ".last_outcome",
            show(named.status) + " (status of the named execution)",
            info.last_outcome);
      }
    }
  }

  // ---- V-07: recorded reviews bounded by executions ----------------
  // Every recorded review attaches to a bridge execution row.
  if (analyst && executions) {
    const n = analyst.reviews_recorded;
    if (!isInt(n) || n < 0 || n > executions.length) {
      add("V-07", "analyst.reviews_recorded",
          "an integer between 0 and " + executions.length +
            " (the execution count)",
          n);
    }
  }

  // ---- V-08: position coherence ------------------------------------
  // The rendered position is the Stage 2 engine's state for the same
  // chain the executions record. Payload vocabulary note: an
  // executed, still-open execution carries row status "OPEN" with a
  // null exit (the bridge's execute_record return value "EXECUTED"
  // is not a stored row status). An open position with no un-exited
  // open execution — or the reverse — is two records of one reality
  // disagreeing.
  if (position && executions) {
    const positionOpen =
      typeof position.side === "string" && position.side.length > 0 &&
      isNum(position.qty) && position.qty !== 0;
    const unExitedOpen = executions.some(
      (e) =>
        isObj(e) && e.status === "OPEN" &&
        (e.exit === null || e.exit === undefined)
    );
    if (positionOpen !== unExitedOpen) {
      add("V-08", "paper.position",
          positionOpen
            ? "an un-exited OPEN execution behind the open position"
            : "a flat position (an un-exited OPEN execution exists)",
          positionOpen ? "open position, none found" : position);
    }
  }

  // ---- V-09: fills are simulated, wherever a fill is evidenced -----
  if (paper && typeof paper.fills_source === "string" &&
      paper.fills_source !== EXPECTED_FILLS_SOURCE) {
    add("V-09", "paper.fills_source", show(EXPECTED_FILLS_SOURCE),
        paper.fills_source);
  }
  if (executions) {
    executions.forEach((e, i) => {
      if (!isObj(e)) return;
      for (const part of ["order", "exit"]) {
        const node = e[part];
        if (!isObj(node)) continue;
        // Where the backend emits a fill (a numeric fill price), the
        // source marker must be the simulated one. Entries without a
        // fill (e.g. a rejection's order entry, whose marker is null)
        // evidence no fill and are not flagged.
        if (isNum(node.fill_price) &&
            node.fill_price_source !== EXPECTED_FILLS_SOURCE) {
          add("V-09",
              "paper.executions[" + i + "]." + part +
                ".fill_price_source",
              show(EXPECTED_FILLS_SOURCE), node.fill_price_source);
        }
      }
    });
  }

  // ---- V-10: EXPLICIT NON-RULE (temporal) ---------------------------
  // risk.automation_paused == true (or kill_switch == true) alongside
  // an EXECUTED/OPEN/CLOSED last_outcome is VALID: the pause is the
  // current state, the outcome is history. This validator must never
  // flag it. There is intentionally no code for V-10 — this comment
  // is the rule, and a valid-combination test pins it.
  //
  // Deliberate non-rules, recorded so nobody "fixes" them later:
  // no identity is asserted between the pipeline counts and
  // paper.journal_entries / the executions total (different journals,
  // legitimately different), and paper.journal_entries >= the
  // execution count is NOT asserted, because the
  // EXECUTED_JOURNAL_FAILED outcome exists precisely for the case
  // where journaling failed after execution.

  return {
    classification: violations.length === 0 ? "fresh" : "contradictory",
    violations,
  };
}

export { validatePaperBridgeStatus };

// Dual export: the bundler uses the ES export above; Node (driven by
// the repo's Python test suite) uses this guard to execute the actual
// shipped function. The guard is inert in the browser bundle.
if (typeof module !== "undefined" && module.exports) {
  module.exports = { validatePaperBridgeStatus };
}
