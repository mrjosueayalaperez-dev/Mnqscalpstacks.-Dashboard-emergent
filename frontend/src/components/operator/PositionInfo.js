import React from "react";
import { Crosshair } from "lucide-react";

export default function PositionInfo({ state, lastPrice }) {
  const pos = state?.position || { side: null, qty: 0, avg_entry: 0 };
  const flat = !pos.side;
  const sideColor = pos.side === "LONG" ? "#34C759" : pos.side === "SHORT" ? "#FF3B30" : "#52525b";

  const ticksFromEntry = (() => {
    if (flat || !lastPrice) return 0;
    const diff = (lastPrice - pos.avg_entry) * (pos.side === "LONG" ? 1 : -1);
    return Math.round(diff * 4); // 1 tick = 0.25 on MNQ
  })();
  const unrealPnl = ticksFromEntry * 0.5 * pos.qty; // $0.50/tick MNQ

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-3" data-testid="position-info">
      <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1.5">
        <Crosshair className="w-3.5 h-3.5" /> Position
      </h3>

      {flat ? (
        <div className="py-4 text-center" data-testid="position-flat">
          <div className="text-[0.7rem] font-black tracking-wider text-zinc-600 mb-1">— FLAT —</div>
          <div className="text-[0.55rem] text-zinc-600">No open position</div>
        </div>
      ) : (
        <div className="space-y-2" data-testid="position-open">
          <div className="flex items-center justify-between">
            <span className="text-xs font-black tracking-wider" style={{ color: sideColor }}>{pos.side}</span>
            <span className="text-xs font-mono font-bold text-white">{pos.qty} MNQ</span>
          </div>
          <div className="border-t border-white/5 pt-2 grid grid-cols-2 gap-2 text-[0.6rem]">
            <div>
              <span className="text-zinc-500 block">Avg Entry</span>
              <span className="font-mono font-bold text-white">{pos.avg_entry.toFixed(2)}</span>
            </div>
            <div>
              <span className="text-zinc-500 block">Last Price</span>
              <span className="font-mono font-bold text-white">{lastPrice ? lastPrice.toFixed(2) : "—"}</span>
            </div>
            <div>
              <span className="text-zinc-500 block">Ticks</span>
              <span className={`font-mono font-bold ${ticksFromEntry >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                {ticksFromEntry >= 0 ? "+" : ""}{ticksFromEntry}
              </span>
            </div>
            <div>
              <span className="text-zinc-500 block">Unrealized</span>
              <span className={`font-mono font-bold ${unrealPnl >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                {unrealPnl >= 0 ? "+" : ""}${unrealPnl.toFixed(2)}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
