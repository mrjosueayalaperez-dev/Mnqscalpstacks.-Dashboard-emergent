import React from "react";
import { Target, Zap, Rocket } from "lucide-react";

/**
 * R-Multiple Ladder — 3 prop-firm-style scalp presets that auto-attach
 * SL/TP brackets to every BUY/SELL order.
 *
 * MNQ: 1 tick = 0.25 pts = $0.50.
 * SL fixed at 40 ticks ($20) to keep risk constant; TP varies by R.
 */
export const PRESETS = [
  { id: "SNIPE_1R", label: "Snipe 1R",  sub: "Scratch defense",  sl: 40, tp: 60,  rr: "1.5R", color: "#34C759", icon: Target, key: "7" },
  { id: "SNIPE_2R", label: "Snipe 2R",  sub: "Target trade",     sl: 40, tp: 120, rr: "3R",   color: "#FFCC00", icon: Zap,    key: "8" },
  { id: "RUNNER",   label: "Runner",    sub: "Let it work",      sl: 40, tp: 200, rr: "5R",   color: "#007AFF", icon: Rocket, key: "9" },
];

export const presetById = (id) => PRESETS.find((p) => p.id === id);

const KeyCap = ({ k }) => (
  <kbd className="px-1.5 py-0.5 text-[0.55rem] font-mono font-black bg-white/10 border border-white/20 rounded text-white">
    {k}
  </kbd>
);

export default function BracketPresets({ activeId, onSelect, brackets }) {
  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-3" data-testid="bracket-presets">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 flex items-center gap-1.5">
          <Target className="w-3.5 h-3.5 text-[#FFCC00]" /> Bracket Presets
        </h3>
        <label className="flex items-center gap-1.5 cursor-pointer" data-testid="brackets-toggle-label">
          <input
            type="checkbox"
            checked={brackets}
            onChange={(e) => onSelect(activeId, e.target.checked)}
            data-testid="brackets-toggle"
            className="accent-[#FFCC00] w-3 h-3"
          />
          <span className="text-[0.55rem] uppercase tracking-wider font-bold text-zinc-400">
            Attach brackets
          </span>
        </label>
      </div>

      <div className="grid grid-cols-3 gap-2">
        {PRESETS.map((p) => {
          const active = activeId === p.id && brackets;
          return (
            <button
              key={p.id}
              onClick={() => onSelect(p.id, true)}
              data-testid={`preset-${p.id.toLowerCase()}`}
              className={`p-2.5 rounded-sm border text-left transition-all ${
                active
                  ? "shadow-[0_0_12px_rgba(255,204,0,0.2)]"
                  : "hover:border-white/30"
              }`}
              style={{
                borderColor: active ? p.color : "rgba(255,255,255,0.1)",
                backgroundColor: active ? `${p.color}15` : "transparent",
              }}
            >
              <div className="flex items-center justify-between mb-1">
                <p.icon className="w-3.5 h-3.5" style={{ color: p.color }} />
                <KeyCap k={p.key} />
              </div>
              <div className="text-[0.65rem] font-black uppercase tracking-wider" style={{ color: active ? p.color : "#fff" }}>
                {p.label}
              </div>
              <div className="text-[0.5rem] text-zinc-500 mb-1">{p.sub}</div>
              <div className="flex items-center justify-between text-[0.55rem] font-mono">
                <span className="text-[#FF3B30]">SL {p.sl}t</span>
                <span className="text-[#34C759]">TP {p.tp}t</span>
              </div>
              <div className="text-[0.5rem] font-mono text-zinc-600 text-right mt-0.5">{p.rr}</div>
            </button>
          );
        })}
      </div>

      <p className="text-[0.5rem] text-zinc-600 mt-2 italic leading-snug">
        Active preset auto-attaches SL/TP to every new BUY/SELL. Closes & break-evens unaffected.
      </p>
    </div>
  );
}
