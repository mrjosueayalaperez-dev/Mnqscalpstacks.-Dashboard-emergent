import React, { useState } from "react";
import { Copy, Check, X, LineChart, Grid3x3, BarChart2, BarChart3 } from "lucide-react";

export const CHART_MODES = [
  { id: "standard", label: "Standard", desc: "TradingView candles + live tape", icon: LineChart },
  { id: "footprint", label: "Footprint", desc: "Buy × sell volume per price cell", icon: Grid3x3 },
  { id: "delta", label: "Delta", desc: "Buy vs sell pressure per bar", icon: BarChart2 },
  { id: "volume_profile", label: "Volume Profile", desc: "Volume at price with POC", icon: BarChart3 },
];

/** NinjaTrader-style blue circle switcher + bottom sheet (mobile) / modal (desktop). */
export const ChartModeSwitcher = ({ mode, onChange }) => {
  const [open, setOpen] = useState(false);

  const select = (id) => {
    onChange(id);
    setOpen(false);
  };

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        aria-label="Switch chart mode"
        className="w-8 h-8 shrink-0 rounded-full bg-[#007AFF] hover:bg-[#0A84FF] flex items-center justify-center shadow-lg shadow-[#007AFF]/40 transition-transform duration-100 active:scale-90"
        data-testid="chart-mode-btn"
      >
        <Copy className="w-4 h-4 text-white" />
      </button>

      {open && (
        <div
          className="fixed inset-0 z-[70] flex items-end sm:items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setOpen(false)}
          data-testid="chart-mode-sheet"
        >
          <div
            className="w-full sm:max-w-sm bg-[#121212] border border-white/10 rounded-t-2xl sm:rounded-sm p-4 pb-6 sm:pb-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-white/20 sm:hidden" />
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-black tracking-wider text-white">CHART MODE</h3>
              <button
                onClick={() => setOpen(false)}
                className="p-1.5 rounded-sm hover:bg-white/10 transition-colors"
                data-testid="chart-mode-close"
              >
                <X className="w-4 h-4 text-zinc-400" />
              </button>
            </div>
            <div className="space-y-2">
              {CHART_MODES.map((m) => {
                const active = mode === m.id;
                return (
                  <button
                    key={m.id}
                    onClick={() => select(m.id)}
                    className={`w-full flex items-center gap-3 p-3 rounded-sm border text-left transition-colors ${
                      active
                        ? "border-[#007AFF] bg-[#007AFF]/10"
                        : "border-white/10 bg-white/[0.03] hover:bg-white/5"
                    }`}
                    data-testid={`chart-mode-${m.id}`}
                  >
                    <span className={`w-9 h-9 rounded-full flex items-center justify-center shrink-0 ${active ? "bg-[#007AFF]" : "bg-white/10"}`}>
                      <m.icon className={`w-4 h-4 ${active ? "text-white" : "text-zinc-400"} ${m.id === "volume_profile" ? "rotate-90" : ""}`} />
                    </span>
                    <span className="flex-1 min-w-0">
                      <span className={`block text-sm font-bold ${active ? "text-[#007AFF]" : "text-white"}`}>{m.label}</span>
                      <span className="block text-[0.65rem] text-zinc-500">{m.desc}</span>
                    </span>
                    {active && <Check className="w-4 h-4 text-[#007AFF] shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>
      )}
    </>
  );
};

export default ChartModeSwitcher;
