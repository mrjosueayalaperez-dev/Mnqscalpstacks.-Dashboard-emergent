import React from "react";
import { Activity, BarChart3, RefreshCw } from "lucide-react";

export const Header = ({ onRefresh, lastUpdate }) => (
  <header className="h-12 md:h-14 border-b border-white/10 bg-[#0A0A0A]/90 backdrop-blur-xl flex items-center justify-between px-3 md:px-4 sticky top-0 z-50" data-testid="main-header">
    <div className="flex items-center gap-2 md:gap-3">
      <div className="flex items-center gap-1.5">
        <Activity className="w-5 h-5 text-[#007AFF]" />
        <h1 className="text-sm md:text-base font-black tracking-tight">MNQ COMMAND CENTER</h1>
      </div>
      <div className="w-2 h-2 bg-[#34C759] rounded-full animate-pulse hidden md:block" />
    </div>
    <div className="hidden lg:flex items-center gap-1">
      {["Signals", "Automation", "Education", "Broker Tools"].map((tab) => (
        <span key={tab} className="px-2 py-1 text-[0.6rem] text-zinc-500 hover:text-white cursor-pointer transition-colors">{tab}</span>
      ))}
    </div>
    <div className="flex items-center gap-2 md:gap-3">
      <a href="/performance" className="hidden md:flex items-center gap-1 px-2.5 py-1 text-[0.65rem] bg-[#FFCC00]/15 text-[#FFCC00] rounded-sm hover:bg-[#FFCC00]/25 transition-colors font-bold" data-testid="performance-link">
        <BarChart3 className="w-3 h-3" /> Performance
      </a>
      <a href="/performance" className="hidden sm:flex items-center gap-1 px-2.5 py-1 text-[0.65rem] bg-[#34C759] text-black rounded-sm hover:bg-[#2DB84E] transition-colors font-bold" data-testid="upgrade-pro-btn">
        Upgrade Pro
      </a>
      <span className="text-[0.6rem] text-zinc-600 font-mono hidden md:inline">{lastUpdate || ""}</span>
      <button onClick={onRefresh} className="p-1.5 hover:bg-white/5 rounded transition-colors" data-testid="refresh-all-btn">
        <RefreshCw className="w-3.5 h-3.5 text-zinc-400" />
      </button>
    </div>
  </header>
);
