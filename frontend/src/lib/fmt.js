/** Shared honesty helpers: never render a missing metric as 0%, always label data mode. */
export const DATA_MODE = "PAPER / SIM / TEST";
export const DATA_MODE_NOTE = "Paper/simulated test data — not live trading results and not proof of performance.";
export const fmtPct = (v) => (v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : `${v}%`);
export const fmtNum = (v, pre = "", post = "") => (v === null || v === undefined || Number.isNaN(Number(v)) ? "—" : `${pre}${v}${post}`);
export const hasNum = (v) => v !== null && v !== undefined && !Number.isNaN(Number(v));
