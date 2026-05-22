import React from "react";
import { Shield, AlertTriangle, Clock } from "lucide-react";

const Bar = ({ value, max, color }) => {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className="h-1.5 bg-white/5 rounded-full overflow-hidden">
      <div className="h-full transition-all" style={{ width: `${pct}%`, backgroundColor: color }} />
    </div>
  );
};

export default function RiskPanel({ state }) {
  const pnl = state?.daily_pnl || 0;
  const maxLoss = state?.max_daily_loss || -1000;
  const trades = state?.daily_trades || 0;
  const maxTrades = state?.max_daily_trades || 20;
  const cooldown = state?.cooldown_ms_remaining || 0;
  const killed = state?.kill_switch;
  const paused = state?.automation_paused;
  const marketOpen = state?.market_open;

  const lossPct = Math.min(1, Math.abs(Math.min(pnl, 0)) / Math.abs(maxLoss));
  const lossColor = lossPct >= 0.75 ? "#FF3B30" : lossPct >= 0.5 ? "#FFCC00" : "#34C759";
  const tradesColor = trades >= maxTrades * 0.75 ? "#FF3B30" : trades >= maxTrades * 0.5 ? "#FFCC00" : "#34C759";

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-3 space-y-3" data-testid="risk-panel">
      <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 flex items-center gap-1.5">
        <Shield className="w-3.5 h-3.5 text-[#FFCC00]" /> Risk Gates
      </h3>

      {/* Loss gauge */}
      <div data-testid="risk-loss-gauge">
        <div className="flex justify-between text-[0.55rem] mb-1">
          <span className="text-zinc-500">Daily Loss</span>
          <span className="font-mono" style={{ color: lossColor }}>
            ${Math.min(pnl, 0).toFixed(2)} / ${maxLoss}
          </span>
        </div>
        <Bar value={Math.abs(Math.min(pnl, 0))} max={Math.abs(maxLoss)} color={lossColor} />
      </div>

      {/* Trades counter */}
      <div data-testid="risk-trades-gauge">
        <div className="flex justify-between text-[0.55rem] mb-1">
          <span className="text-zinc-500">Trades Today</span>
          <span className="font-mono" style={{ color: tradesColor }}>{trades} / {maxTrades}</span>
        </div>
        <Bar value={trades} max={maxTrades} color={tradesColor} />
      </div>

      {/* Status pills */}
      <div className="grid grid-cols-2 gap-1.5 pt-1">
        <div className="bg-white/5 rounded-sm px-2 py-1 flex items-center justify-between" data-testid="risk-market">
          <span className="text-[0.55rem] text-zinc-500">Market</span>
          <span className={`text-[0.55rem] font-bold ${marketOpen ? "text-[#34C759]" : "text-zinc-600"}`}>
            {marketOpen ? "OPEN" : "CLOSED"}
          </span>
        </div>
        <div className="bg-white/5 rounded-sm px-2 py-1 flex items-center justify-between" data-testid="risk-automation">
          <span className="text-[0.55rem] text-zinc-500">Auto</span>
          <span className={`text-[0.55rem] font-bold ${paused ? "text-[#FFCC00]" : "text-[#34C759]"}`}>
            {paused ? "PAUSED" : "ACTIVE"}
          </span>
        </div>
        <div className="bg-white/5 rounded-sm px-2 py-1 flex items-center justify-between" data-testid="risk-cooldown">
          <span className="text-[0.55rem] text-zinc-500 flex items-center gap-1"><Clock className="w-2.5 h-2.5" />CD</span>
          <span className={`text-[0.55rem] font-mono ${cooldown > 0 ? "text-[#FFCC00]" : "text-zinc-500"}`}>
            {cooldown}ms
          </span>
        </div>
        <div className="bg-white/5 rounded-sm px-2 py-1 flex items-center justify-between" data-testid="risk-kill">
          <span className="text-[0.55rem] text-zinc-500">Kill</span>
          <span className={`text-[0.55rem] font-bold ${killed ? "text-[#FF3B30]" : "text-[#34C759]"}`}>
            {killed ? "ARMED" : "OFF"}
          </span>
        </div>
      </div>

      {killed && (
        <div className="flex items-center gap-1.5 text-[0.55rem] text-[#FF3B30] font-bold animate-pulse">
          <AlertTriangle className="w-3 h-3" /> KILL SWITCH ACTIVE — ALL ORDERS BLOCKED
        </div>
      )}
    </div>
  );
}
