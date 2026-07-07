import React, { useEffect, useState, useCallback } from "react";
import axios from "axios";
import { Layers, ArrowUp, ArrowDown, TrendingUp, TrendingDown, Activity } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const COLOR = { green: "#34C759", red: "#FF3B30", yellow: "#FFCC00", muted: "#9ca3af" };

const pdhPillColor = (ctx) => {
  if (ctx.is_above_pdh) return COLOR.green;
  if (ctx.ticks_from_pdh > -40) return COLOR.yellow;
  return COLOR.muted;
};
const pdlPillColor = (ctx) => {
  if (ctx.is_below_pdl) return COLOR.red;
  if (ctx.ticks_from_pdl < 40) return COLOR.yellow;
  return COLOR.muted;
};
const trendColor = (pct) => {
  if (pct > 0.5) return COLOR.green;
  if (pct < -0.5) return COLOR.red;
  return COLOR.yellow;
};
const rangeColor = (ctx) => {
  if (ctx.is_range_extended) return COLOR.red;
  if (ctx.range_expansion_pct > 80) return COLOR.yellow;
  return COLOR.green;
};
const volumeColor = (pct) => {
  if (pct > 100) return COLOR.green;
  if (pct < 60) return COLOR.red;
  return COLOR.yellow;
};

const Row = ({ label, value, color, sub, testId }) => (
  <div className="flex items-center justify-between" data-testid={testId}>
    <span className="text-zinc-500">{label}</span>
    <div className="text-right">
      <div className="font-mono font-bold" style={{ color: color || "#fff" }}>{value}</div>
      {sub && <div className="text-[0.5rem] text-zinc-600">{sub}</div>}
    </div>
  </div>
);

export default function MarketContext() {
  const [ctx, setCtx] = useState(null);
  const [err, setErr] = useState(false);

  const load = useCallback(async () => {
    try {
      const { data } = await axios.get(`${API}/market/context`);
      setCtx(data);
      setErr(false);
    } catch (e) {
      setErr(true);
    }
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 60000);  // refresh every minute
    return () => clearInterval(id);
  }, [load]);

  if (err) {
    return (
      <div className="bg-[#121212] border border-white/10 rounded-sm p-3" data-testid="market-context-error">
        <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 flex items-center gap-1.5 mb-1">
          <Layers className="w-3.5 h-3.5 text-[#a855f7]" /> Market Context
        </h3>
        <div className="text-[0.55rem] text-zinc-600 italic">Context feed unavailable.</div>
      </div>
    );
  }
  if (!ctx) {
    return (
      <div className="bg-[#121212] border border-white/10 rounded-sm p-3 text-[0.55rem] text-zinc-600" data-testid="market-context-loading">
        Loading context…
      </div>
    );
  }

  // Color logic (via helpers above to avoid nested ternaries)
  const pdhColor = pdhPillColor(ctx);
  const pdlColor = pdlPillColor(ctx);
  const trendCol = trendColor(ctx.trend_5d_pct);
  const rangeCol = rangeColor(ctx);
  const volCol = volumeColor(ctx.volume_strength_pct);

  // Position-in-day bar
  const pos = Math.min(100, Math.max(0, ctx.pos_in_day_pct));

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-3 space-y-2.5" data-testid="market-context">
      <div className="flex items-center justify-between">
        <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 flex items-center gap-1.5">
          <Layers className="w-3.5 h-3.5 text-[#a855f7]" /> Market Context
        </h3>
        <span className="text-[0.5rem] text-zinc-600">10d daily</span>
      </div>

      {/* Prior session anchors */}
      <div className="space-y-1.5 text-[0.6rem]" data-testid="context-prior-session">
        <Row
          label="PDH"
          value={ctx.prior_high.toFixed(2)}
          color={pdhColor}
          sub={`${ctx.ticks_from_pdh >= 0 ? "+" : ""}${ctx.ticks_from_pdh}t`}
          testId="context-pdh"
        />
        <Row
          label="PDL"
          value={ctx.prior_low.toFixed(2)}
          color={pdlColor}
          sub={`${ctx.ticks_from_pdl >= 0 ? "+" : ""}${ctx.ticks_from_pdl}t`}
          testId="context-pdl"
        />
        <Row
          label="PDC"
          value={ctx.prior_close.toFixed(2)}
          color="#9ca3af"
          testId="context-pdc"
        />
      </div>

      {/* Today's range */}
      <div className="border-t border-white/5 pt-2" data-testid="context-today">
        <div className="flex items-center justify-between text-[0.6rem] mb-1">
          <span className="text-zinc-500">Today Range</span>
          <span className="font-mono" style={{ color: rangeCol }}>
            {ctx.today_range_points}p
          </span>
        </div>
        <div className="flex items-center justify-between text-[0.55rem] mb-1">
          <span className="text-zinc-600">vs ADR(5) {ctx.adr5}p</span>
          <span className="font-mono font-bold" style={{ color: rangeCol }}>
            {ctx.range_expansion_pct}%
          </span>
        </div>
        <div className="h-1 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full transition-all"
            style={{ width: `${Math.min(100, ctx.range_expansion_pct)}%`, backgroundColor: rangeCol }}
          />
        </div>
      </div>

      {/* Position within day */}
      <div data-testid="context-day-position">
        <div className="flex items-center justify-between text-[0.55rem] mb-1">
          <span className="text-zinc-500">Day Range Position</span>
          <span className="font-mono text-zinc-300">{ctx.pos_in_day_pct}%</span>
        </div>
        <div className="relative h-2 bg-white/5 rounded-sm overflow-hidden">
          <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-[#FF3B30]/30 via-[#FFCC00]/30 to-[#34C759]/30 w-full" />
          <div
            className="absolute top-0 bottom-0 w-0.5 bg-white shadow-[0_0_4px_rgba(255,255,255,0.8)]"
            style={{ left: `calc(${pos}% - 1px)` }}
          />
        </div>
        <div className="flex justify-between text-[0.5rem] text-zinc-600 mt-0.5 font-mono">
          <span>L {ctx.today_low}</span>
          <span>H {ctx.today_high}</span>
        </div>
      </div>

      {/* Trend + Volume */}
      <div className="border-t border-white/5 pt-2 grid grid-cols-2 gap-2 text-[0.55rem]">
        <div data-testid="context-trend">
          <div className="text-zinc-500 mb-0.5 flex items-center gap-1">
            {ctx.trend_5d_pct >= 0 ? <TrendingUp className="w-2.5 h-2.5" /> : <TrendingDown className="w-2.5 h-2.5" />}
            5d Trend
          </div>
          <div className="font-mono font-bold" style={{ color: trendCol }}>
            {ctx.trend_5d_pct >= 0 ? "+" : ""}{ctx.trend_5d_pct}%
          </div>
        </div>
        <div data-testid="context-volume">
          <div className="text-zinc-500 mb-0.5 flex items-center gap-1">
            <Activity className="w-2.5 h-2.5" /> Vol vs 5dAvg
          </div>
          <div
            className="font-mono font-bold"
            style={{ color: volCol }}
          >
            {ctx.volume_strength_pct}%
          </div>
        </div>
      </div>

      {/* Status flags */}
      <div className="flex flex-wrap gap-1 pt-1 border-t border-white/5">
        {ctx.is_above_pdh && (
          <span className="px-1.5 py-0.5 text-[0.5rem] font-black bg-[#34C759]/15 text-[#34C759] rounded-sm flex items-center gap-1" data-testid="context-flag-above-pdh">
            <ArrowUp className="w-2 h-2" /> ABOVE PDH
          </span>
        )}
        {ctx.is_below_pdl && (
          <span className="px-1.5 py-0.5 text-[0.5rem] font-black bg-[#FF3B30]/15 text-[#FF3B30] rounded-sm flex items-center gap-1" data-testid="context-flag-below-pdl">
            <ArrowDown className="w-2 h-2" /> BELOW PDL
          </span>
        )}
        {ctx.is_range_extended && (
          <span className="px-1.5 py-0.5 text-[0.5rem] font-black bg-[#FFCC00]/15 text-[#FFCC00] rounded-sm" data-testid="context-flag-extended">
            ⚠ RANGE EXT
          </span>
        )}
        {!ctx.is_above_pdh && !ctx.is_below_pdl && !ctx.is_range_extended && (
          <span className="px-1.5 py-0.5 text-[0.5rem] font-bold bg-white/5 text-zinc-500 rounded-sm" data-testid="context-flag-inrange">
            IN PRIOR RANGE
          </span>
        )}
      </div>
    </div>
  );
}
