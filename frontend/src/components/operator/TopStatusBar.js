import React from "react";
import { Activity, Power, Wifi, WifiOff } from "lucide-react";

const fmtSec = (s) => {
  const h = Math.floor(s / 3600).toString().padStart(2, "0");
  const m = Math.floor((s % 3600) / 60).toString().padStart(2, "0");
  const sec = (s % 60).toString().padStart(2, "0");
  return `${h}:${m}:${sec}`;
};

export default function TopStatusBar({ state, onFlatten }) {
  const connected = state?.connection?.status === "CONNECTED";
  const pnl = state?.daily_pnl || 0;
  const balance = state?.balance || 0;
  const sessionSec = state?.session_seconds || 0;
  const broker = state?.connection?.broker || "NinjaTrader";
  const account = state?.connection?.account || "—";

  return (
    <header
      data-testid="operator-topbar"
      className="h-12 border-b border-white/10 bg-[#0A0A0A] flex items-center justify-between px-3 md:px-4 sticky top-0 z-50"
    >
      {/* LEFT: Logo */}
      <div className="flex items-center gap-2 min-w-0">
        <div className="relative w-6 h-6 shrink-0">
          <Activity className="w-6 h-6 text-[#34C759] absolute animate-pulse" />
        </div>
        <div className="leading-tight">
          <div className="text-[0.7rem] font-black tracking-tight text-white">MNQ SCALP STACKS</div>
          <div className="text-[0.5rem] font-bold tracking-wider text-[#34C759]">OPERATOR COCKPIT</div>
        </div>
      </div>

      {/* CENTER: Connection */}
      <div className="hidden md:flex items-center gap-2" data-testid="connection-status">
        <div className={`w-2 h-2 rounded-full ${connected ? "bg-[#34C759] animate-pulse" : "bg-[#FF3B30]"}`} />
        {connected ? <Wifi className="w-3 h-3 text-[#34C759]" /> : <WifiOff className="w-3 h-3 text-[#FF3B30]" />}
        <span className={`text-[0.6rem] font-black tracking-wider ${connected ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
          {connected ? "CONNECTED" : "DISCONNECTED"} • {broker} {account}
        </span>
      </div>

      {/* RIGHT: stats + flatten */}
      <div className="flex items-center gap-2 md:gap-4">
        <div className="hidden sm:block text-right">
          <div className="text-[0.5rem] font-bold tracking-wider text-zinc-500">BALANCE</div>
          <div className="text-xs font-mono font-bold text-white" data-testid="topbar-balance">${balance.toLocaleString()}</div>
        </div>
        <div className="text-right">
          <div className="text-[0.5rem] font-bold tracking-wider text-zinc-500">DAILY PNL</div>
          <div
            className={`text-xs font-mono font-bold ${pnl > 0 ? "text-[#34C759]" : pnl < 0 ? "text-[#FF3B30]" : "text-zinc-300"}`}
            data-testid="topbar-pnl"
          >
            {pnl >= 0 ? "+" : ""}${pnl.toFixed(2)}
          </div>
        </div>
        <div className="hidden sm:block text-right">
          <div className="text-[0.5rem] font-bold tracking-wider text-zinc-500">SESSION</div>
          <div className="text-xs font-mono text-zinc-300" data-testid="topbar-session">{fmtSec(sessionSec)}</div>
        </div>

        <button
          onClick={onFlatten}
          data-testid="flatten-btn"
          className="px-3 md:px-4 py-1.5 bg-[#FF3B30] hover:bg-[#FF5447] active:bg-[#CC2F26] text-white text-[0.6rem] md:text-[0.7rem] font-black uppercase tracking-wider rounded-sm transition-colors flex items-center gap-1.5 shadow-[0_0_20px_rgba(255,59,48,0.3)]"
        >
          <Power className="w-3 h-3 md:w-3.5 md:h-3.5" />
          <span className="hidden sm:inline">FLATTEN</span>
          <span className="sm:hidden">FLAT</span>
        </button>
      </div>
    </header>
  );
}
