import React, { useCallback, useEffect, useState } from "react";
import axios from "axios";
import { Activity, BookOpen, Shield } from "lucide-react";
import { validatePaperBridgeStatus } from "./paperBridgeStatusValidation";

// Paper Bridge panel — renders GET /api/paper-bridge/status and nothing
// else. Every figure on this panel is read from that endpoint's payload
// at render time; the panel computes no market data and invents no
// defaults. If the endpoint has not returned data, the panel shows an
// explicit unavailable state instead of figures.
//
// Truth-in-labeling rules for this surface (enforced by
// backend/tests/test_paper_bridge_panel.py): the environment is PAPER,
// every fill is SIMULATED, the provider state is shown exactly as the
// payload states it, and the risk approval state is shown verbatim.

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const EXECUTED_FAMILY = ["EXECUTED", "OPEN", "CLOSED", "EXECUTED_JOURNAL_FAILED"];

const shortId = (id) => (id ? `${id.slice(0, 12)}…` : "—");

const num = (v, digits = 2) =>
  typeof v === "number" && Number.isFinite(v) ? v.toFixed(digits) : "—";

const Row = ({ label, children, testId }) => (
  <div className="flex items-center justify-between gap-2" data-testid={testId}>
    <span className="text-zinc-500 shrink-0">{label}</span>
    <span className="font-mono text-zinc-200 text-right truncate">{children}</span>
  </div>
);

const SectionTitle = ({ children, testId }) => (
  <h4
    className="text-[0.55rem] font-black uppercase tracking-wider text-zinc-500 mb-1"
    data-testid={testId}
  >
    {children}
  </h4>
);

function StrategyBlock({ title, info, latestSignalId, testId }) {
  return (
    <div data-testid={testId}>
      <SectionTitle>{title}</SectionTitle>
      {!info && (
        <div className="text-zinc-600 italic">No executions recorded.</div>
      )}
      {info && (
        <div className="space-y-0.5">
          <Row label="Last outcome">{info.last_outcome || "—"}</Row>
          <Row label="Last signal">
            <span title={info.last_signal_id || undefined}>
              {shortId(info.last_signal_id)}
            </span>
          </Row>
          {info.last_reason && <Row label="Reason">{info.last_reason}</Row>}
        </div>
      )}
      <div className="space-y-0.5 mt-1">
        <Row label="Latest qualified signal">
          <span title={latestSignalId || undefined}>{shortId(latestSignalId)}</span>
        </Row>
      </div>
    </div>
  );
}

export default function PaperBridgePanel() {
  const [status, setStatus] = useState(null);
  const [validation, setValidation] = useState(null);

  const refresh = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/paper-bridge/status`);
      // PV-06: validate the payload's internal consistency before it
      // is rendered. A contradictory payload fails closed (the
      // INVALID state below); its figures are never shown as status.
      const verdict = validatePaperBridgeStatus(data);
      if (verdict.classification === "contradictory") {
        console.warn(
          "[PaperBridge] contradictory status payload:",
          verdict.violations
        );
      }
      setValidation(verdict);
      setStatus(data);
    } catch (e) {
      // Endpoint unreachable: drop any prior payload so stale figures
      // are never dressed up as current state.
      setStatus(null);
      console.warn("[PaperBridge] status refresh failed:", e?.message || e);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  if (!status) {
    return (
      <div
        className="bg-[#121212] border border-white/10 rounded-sm p-3"
        data-testid="paper-bridge-panel"
      >
        <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-[#FFCC00]" />
          Paper Trading — Signal Bridge · PAPER · SIMULATED
        </h3>
        <div
          className="text-center py-3 text-[0.55rem] text-zinc-500 italic"
          data-testid="pb-unavailable"
        >
          PAPER BRIDGE STATUS UNAVAILABLE — the status endpoint has not
          returned data. No figures are shown, because none have been
          received.
        </div>
      </div>
    );
  }

  if (validation && validation.classification === "contradictory") {
    // Fail closed: the payload's fields contradict each other, so no
    // figure from it is rendered as status. The violations are shown
    // as diagnostic evidence only — labeled, under the INVALID
    // heading — never as authoritative values.
    return (
      <div
        className="bg-[#121212] border border-white/10 rounded-sm p-3"
        data-testid="paper-bridge-panel"
      >
        <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
          <Activity className="w-3.5 h-3.5 text-[#FFCC00]" />
          Paper Trading — Signal Bridge · PAPER · SIMULATED
        </h3>
        <div
          className="text-center py-3 text-[0.55rem] text-zinc-500"
          data-testid="pb-invalid"
        >
          <div className="font-black tracking-wider text-[#FF3B30] not-italic">
            PAPER BRIDGE STATUS INVALID — INCONSISTENT PAYLOAD
          </div>
          <div className="italic mt-1">
            The status endpoint returned data whose fields contradict
            each other. No figures are shown, because none can be
            trusted. Diagnostics below identify the conflicting fields;
            the payload continues to refresh every 5 seconds.
          </div>
          <div
            className="text-left font-mono text-zinc-400 mt-2 space-y-0.5"
            data-testid="pb-invalid-diagnostics"
          >
            {validation.violations.map((v, i) => (
              <div key={i}>
                {v.rule} · {v.field} · expected {v.expected} · actual{" "}
                {v.actual}
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const pipeline = status.pipeline || {};
  const strategies = status.strategies || {};
  const analyst = status.analyst || {};
  const paper = status.paper || {};
  const risk = status.risk || {};
  const connectivity = status.connectivity || {};
  const profile = risk.paper_profile || {};
  const position = paper.position || {};
  const executions = paper.executions || [];
  const latestQualified = pipeline.latest_qualified_signal_id || {};

  const executedCount = executions.filter((e) =>
    EXECUTED_FAMILY.includes(e.status)
  ).length;
  const rejectedCount = executions.filter(
    (e) => e.status === "REJECTED"
  ).length;
  const hasPosition = !!position.side;

  return (
    <div
      className="bg-[#121212] border border-white/10 rounded-sm p-3"
      data-testid="paper-bridge-panel"
    >
      <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
        <Activity className="w-3.5 h-3.5 text-[#FFCC00]" />
        Paper Trading — Signal Bridge
        <span className="px-1 py-0 text-[0.5rem] font-black tracking-wider rounded bg-[#FFCC00]/15 text-[#FFCC00]">
          {status.environment || "PAPER"}
        </span>
        <span className="px-1 py-0 text-[0.5rem] font-black tracking-wider rounded bg-[#FFCC00]/15 text-[#FFCC00]">
          DATA: {status.data_label || "PAPER"}
        </span>
        <span className="px-1 py-0 text-[0.5rem] font-black tracking-wider rounded bg-white/10 text-zinc-300">
          SIMULATED FILLS ONLY
        </span>
      </h3>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-[0.55rem]">
        {/* Pipeline */}
        <div data-testid="pb-pipeline">
          <SectionTitle>Signal Pipeline</SectionTitle>
          <div className="space-y-0.5">
            <Row label="Records journaled">
              {typeof pipeline.records_journaled === "number"
                ? pipeline.records_journaled
                : "—"}
            </Row>
            <Row label="Rejections journaled">
              {typeof pipeline.rejections_journaled === "number"
                ? pipeline.rejections_journaled
                : "—"}
            </Row>
            <Row label="Bridge journal entries">
              {typeof paper.journal_entries === "number"
                ? paper.journal_entries
                : "—"}
            </Row>
            {pipeline.error && (
              <Row label="Pipeline error">{pipeline.error}</Row>
            )}
          </div>
        </div>

        {/* Strategies */}
        <div data-testid="pb-strategy-a">
          <StrategyBlock
            title="Strategy A — Six Gates"
            info={strategies.STRATEGY_A}
            latestSignalId={latestQualified.STRATEGY_A}
            testId="pb-strategy-a-body"
          />
        </div>
        <div data-testid="pb-strategy-b">
          <StrategyBlock
            title="Strategy B — Outer Range"
            info={strategies.STRATEGY_B}
            latestSignalId={latestQualified.STRATEGY_B}
            testId="pb-strategy-b-body"
          />
        </div>

        {/* Analyst */}
        <div data-testid="pb-analyst">
          <SectionTitle>Analyst</SectionTitle>
          <div className="space-y-0.5">
            <Row label="Provider">{analyst.provider_status || "—"}</Row>
            <Row label="Reviews recorded">
              {typeof analyst.reviews_recorded === "number"
                ? analyst.reviews_recorded
                : "—"}
            </Row>
            <div className="text-zinc-500">
              Explanation source
              <div className="font-mono text-zinc-300 break-all">
                {analyst.explanation_source || "—"}
              </div>
            </div>
          </div>
        </div>

        {/* Outcomes: qualified vs rejected, counted from the payload's
            own execution records */}
        <div data-testid="pb-outcomes">
          <SectionTitle>Bridge Outcomes</SectionTitle>
          <div className="space-y-0.5">
            <Row label="Executed / open / closed">{executedCount}</Row>
            <Row label="Rejected">{rejectedCount}</Row>
            <Row label="Execution records">{executions.length}</Row>
          </div>
        </div>

        {/* Paper position */}
        <div data-testid="pb-position">
          <SectionTitle>
            <span className="flex items-center gap-1">
              <BookOpen className="w-3 h-3 text-[#a855f7]" /> Paper Position —
              SIM
            </span>
          </SectionTitle>
          {!hasPosition && (
            <div className="text-zinc-600 italic">
              No open paper position.
            </div>
          )}
          {hasPosition && (
            <div className="space-y-0.5">
              <Row label="Side">{position.side}</Row>
              <Row label="Qty">
                {typeof position.qty === "number" ? position.qty : "—"}
              </Row>
              <Row label="Avg entry (SIM)">{num(position.avg_entry)}</Row>
              <Row label="Stop (SIM)">{num(position.sl_price)}</Row>
              <Row label="Target (SIM)">{num(position.tp_price)}</Row>
              <Row label="Unrealized PnL (SIM)">
                {num(position.unrealized_pnl)}
              </Row>
            </div>
          )}
        </div>

        {/* Risk */}
        <div data-testid="pb-risk">
          <SectionTitle>
            <span className="flex items-center gap-1">
              <Shield className="w-3 h-3 text-[#FF3B30]" /> Risk State
            </span>
          </SectionTitle>
          <div className="space-y-0.5">
            <Row label="Automation">
              {risk.automation_paused ? "PAUSED" : "NOT PAUSED"}
            </Row>
            <Row label="Automated entries">
              {risk.automated_entries || "—"}
            </Row>
            <Row label="Kill switch">{risk.kill_switch ? "ON" : "OFF"}</Row>
            <Row label="Approval">{risk.risk_approval_status || "—"}</Row>
            <Row label="Paper profile qty">
              {typeof profile.qty === "number" ? profile.qty : "—"}
            </Row>
            <Row label="Paper target (R)">
              {typeof profile.target_r === "number" ? profile.target_r : "—"}
            </Row>
            <Row label="Max order qty">
              {typeof risk.max_order_qty === "number"
                ? risk.max_order_qty
                : "—"}
            </Row>
            <Row label="Max bracket (ticks)">
              {typeof risk.max_bracket_ticks === "number"
                ? risk.max_bracket_ticks
                : "—"}
            </Row>
            <Row label="Daily trades">
              {typeof risk.daily_trades === "number" ? risk.daily_trades : "—"}
              {" / "}
              {typeof risk.max_daily_trades === "number"
                ? risk.max_daily_trades
                : "—"}
            </Row>
            <Row label="Daily PnL / max loss">
              {num(risk.daily_pnl)}
              {" / "}
              {num(risk.max_daily_loss)}
            </Row>
          </div>
        </div>

        {/* Connectivity — stated exactly as the payload states it */}
        <div data-testid="pb-connectivity">
          <SectionTitle>Connectivity</SectionTitle>
          <div className="space-y-0.5">
            <Row label="Provider">{connectivity.provider || "—"}</Row>
            <Row label="Fills source">{paper.fills_source || "—"}</Row>
            <div className="text-zinc-500">
              Market data
              <div className="font-mono text-zinc-300">
                {connectivity.market_data || "—"}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Simulated order / fill history */}
      <div className="mt-3" data-testid="pb-history">
        <SectionTitle>
          Simulated Order / Fill History — all fills {paper.fills_source || "SIMULATED"}
        </SectionTitle>
        <div className="space-y-1 max-h-44 overflow-y-auto">
          {executions.length === 0 && (
            <div className="text-center py-2 text-[0.55rem] text-zinc-600 italic">
              No bridge executions recorded.
            </div>
          )}
          {executions.map((e, i) => (
            <div
              key={e.signal_id || i}
              className="bg-white/[0.02] rounded-sm px-2 py-1.5 text-[0.55rem]"
              data-testid={`pb-execution-${i}`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="flex items-center gap-2 min-w-0">
                  <span className="font-mono text-zinc-500" title={e.signal_id}>
                    {shortId(e.signal_id)}
                  </span>
                  <span className="font-black tracking-wider text-zinc-300">
                    {e.strategy_id || "—"}
                  </span>
                  <span className="font-black tracking-wider text-[#FFCC00]">
                    {e.status || "—"}
                  </span>
                  {e.reason && (
                    <span className="text-zinc-500 truncate">{e.reason}</span>
                  )}
                </span>
                {e.order && (
                  <span className="font-mono text-zinc-400 shrink-0">
                    {typeof e.order.qty === "number" ? `x${e.order.qty} ` : ""}
                    {typeof e.order.fill_price === "number"
                      ? `@${e.order.fill_price.toFixed(2)} `
                      : ""}
                    <span className="text-[#FFCC00]">
                      {e.order.fill_price_source || "SIMULATED"}
                    </span>
                  </span>
                )}
              </div>
              {(e.order?.sl_price || e.order?.tp_price) && (
                <div className="flex items-center gap-3 ml-12 mt-0.5 font-mono text-[0.5rem]">
                  {typeof e.order.sl_price === "number" && (
                    <span className="text-[#FF3B30]">
                      SL {e.order.sl_price.toFixed(2)}
                    </span>
                  )}
                  {typeof e.order.tp_price === "number" && (
                    <span className="text-[#34C759]">
                      TP {e.order.tp_price.toFixed(2)}
                    </span>
                  )}
                </div>
              )}
              {e.exit && (
                <div className="ml-12 mt-0.5 font-mono text-[0.5rem] text-zinc-500">
                  Exit (SIM): {e.exit.exit_reason || "—"}
                  {typeof e.exit.fill_price === "number"
                    ? ` @${e.exit.fill_price.toFixed(2)}`
                    : ""}
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
