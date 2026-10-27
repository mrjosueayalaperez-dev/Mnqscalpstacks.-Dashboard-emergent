/** Shared honesty helpers: never render a missing metric as 0%, always label data mode. */
export const DATA_MODE = "PAPER / SIM / TEST";
export const DATA_MODE_NOTE = "Paper/simulated test data — not live trading results and not proof of performance.";
export const fmtPct = (v) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : `${v}%`);
export const fmtNum = (v, pre = "", post = "") => (v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : `${pre}${v}${post}`);
/** Feed label: REAL-TIME only for the licensed TradingView tape when TV_DATA_MODE=realtime.
 *  Yahoo (or anything else) is never "live". */
export const feedLabel = (tick) =>
  tick?.source === "tradingview:live" && tick?.data_mode === "realtime" ? "REAL-TIME" : "DELAYED 10m";
export const RISK_DISCLAIMER =
  "Futures trading involves substantial risk of loss and is not suitable for all investors. This is education and structured practice, not financial advice. Past performance is not indicative of future results.";
export const SIGNALS_NOTE = "PAPER signals · display-only · no orders are placed automatically.";
export const SIM = "SIM";
export const PAPER = "PAPER";
export const hasNum = (v) => v !== null && v !== undefined && !Number.isNaN(Number(v));
