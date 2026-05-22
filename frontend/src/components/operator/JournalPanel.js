import React from "react";
import { BookOpen } from "lucide-react";

const sideColor = (a) => {
  if (!a) return "#9ca3af";
  if (a.startsWith("BUY") || a === "CLOSE_SHORT") return "#34C759";
  if (a.startsWith("SELL") || a === "CLOSE_LONG") return "#FF3B30";
  if (a === "BREAK_EVEN") return "#FFCC00";
  if (a === "FLATTEN_ALL") return "#FF3B30";
  return "#9ca3af";
};

const fmtTime = (iso) => {
  if (!iso) return "—";
  return new Date(iso).toLocaleTimeString("en-US", { hour12: false });
};

export default function JournalPanel({ entries }) {
  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-3" data-testid="journal-panel">
      <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
        <BookOpen className="w-3.5 h-3.5 text-[#a855f7]" /> Journal — Today
      </h3>

      <div className="space-y-1 max-h-44 overflow-y-auto">
        {(!entries || entries.length === 0) && (
          <div className="text-center py-3 text-[0.55rem] text-zinc-600 italic" data-testid="journal-empty">
            No orders logged this session.
          </div>
        )}
        {(entries || []).map((e, i) => (
          <div key={e.id || i} className="bg-white/[0.02] rounded-sm px-2 py-1.5 text-[0.55rem]" data-testid={`journal-entry-${i}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 min-w-0">
                <span className="text-zinc-600 font-mono">{fmtTime(e.ts)}</span>
                <span className="font-black tracking-wider" style={{ color: sideColor(e.action) }}>
                  {e.action}
                </span>
                {e.qty && <span className="text-zinc-400 font-mono">x{e.qty}</span>}
                {e.preset && (
                  <span className="px-1 py-0 text-[0.45rem] font-black tracking-wider rounded bg-[#FFCC00]/15 text-[#FFCC00]" data-testid={`journal-preset-${i}`}>
                    {e.preset}
                  </span>
                )}
              </div>
              <span className="font-mono text-zinc-500 shrink-0">
                {e.fill_price ? `@${e.fill_price.toFixed(2)}` : ""}
                {typeof e.daily_pnl === "number" ? ` | PnL ${e.daily_pnl >= 0 ? "+" : ""}${e.daily_pnl.toFixed(0)}` : ""}
              </span>
            </div>
            {(e.sl_price || e.tp_price) && (
              <div className="flex items-center gap-3 ml-12 mt-0.5 font-mono text-[0.5rem]" data-testid={`journal-bracket-${i}`}>
                {e.sl_price && <span className="text-[#FF3B30]">SL {e.sl_price.toFixed(2)} ({e.sl_ticks}t)</span>}
                {e.tp_price && <span className="text-[#34C759]">TP {e.tp_price.toFixed(2)} ({e.tp_ticks}t)</span>}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
