import React, { useEffect, useState } from "react";
import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Pill = ({ label, price, ticks, color, testId }) => {
  const arrow = ticks > 0 ? "▲" : ticks < 0 ? "▼" : "—";
  return (
    <div
      className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm border bg-[#0F0F0F]"
      style={{ borderColor: `${color}55` }}
      data-testid={testId}
      title={`${label} @ ${price?.toFixed(2)} • ${ticks > 0 ? "+" : ""}${ticks}t from current`}
    >
      <span className="text-[0.55rem] font-black tracking-wider" style={{ color }}>{label}</span>
      <span className="text-[0.55rem] font-mono text-zinc-200">{price?.toFixed(2) ?? "—"}</span>
      {typeof ticks === "number" && (
        <span className="text-[0.5rem] font-mono opacity-70" style={{ color }}>
          {arrow}{Math.abs(ticks)}t
        </span>
      )}
    </div>
  );
};

/**
 * KeyLevels — compact strip above the TradingView chart with PDH/PDL/PDC
 * and today's H/L, color-coded by current-price relation.
 *
 * Why a strip instead of lines on the chart: the TradingView Advanced Chart
 * EMBED widget has no programmatic drawing API (that requires the paid
 * Charting Library license). The strip keeps the levels in your eye-line
 * while you watch the candles.
 */
export default function KeyLevels({ currentPrice }) {
  const [ctx, setCtx] = useState(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/market/context`);
        if (active) setCtx(data);
      } catch { /* ignore */ }
    };
    load();
    const id = setInterval(load, 60000);
    return () => { active = false; clearInterval(id); };
  }, []);

  if (!ctx) return null;

  const cur = currentPrice || ctx.current;
  const ticks = (lvl) => (cur && lvl ? Math.round((cur - lvl) * 4) : null);

  // Color by position relative to current price (above current = resistance/green;
  // below = support/red; close-by = yellow caution)
  const colorFor = (lvl) => {
    const t = ticks(lvl);
    if (t === null) return "#9ca3af";
    if (Math.abs(t) < 20) return "#FFCC00";  // within 5 points — alert
    return t > 0 ? "#FF3B30" : "#34C759";    // level above = resistance, below = support
  };

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 border border-white/10 bg-[#0A0A0A]/95 rounded-sm overflow-x-auto"
      data-testid="key-levels-strip"
    >
      <span className="text-[0.5rem] font-black tracking-wider text-zinc-500 shrink-0">KEY LEVELS</span>
      <Pill label="PDH"   price={ctx.prior_high} ticks={ticks(ctx.prior_high)} color={colorFor(ctx.prior_high)} testId="kl-pdh" />
      <Pill label="PDL"   price={ctx.prior_low}  ticks={ticks(ctx.prior_low)}  color={colorFor(ctx.prior_low)}  testId="kl-pdl" />
      <Pill label="PDC"   price={ctx.prior_close} ticks={ticks(ctx.prior_close)} color={colorFor(ctx.prior_close)} testId="kl-pdc" />
      <Pill label="DAY H" price={ctx.today_high} ticks={ticks(ctx.today_high)} color={colorFor(ctx.today_high)} testId="kl-dayh" />
      <Pill label="DAY L" price={ctx.today_low}  ticks={ticks(ctx.today_low)}  color={colorFor(ctx.today_low)}  testId="kl-dayl" />
      <Pill label="OPEN"  price={ctx.today_open} ticks={ticks(ctx.today_open)} color={colorFor(ctx.today_open)} testId="kl-open" />
    </div>
  );
}
