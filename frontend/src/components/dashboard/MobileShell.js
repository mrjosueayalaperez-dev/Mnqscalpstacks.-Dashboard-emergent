import React, { useState } from "react";
import { ChevronDown, LayoutGrid } from "lucide-react";

export const RiskDisclaimer = () => (
  <p className="col-span-1 md:col-span-4 lg:col-span-12 text-[0.55rem] leading-relaxed text-zinc-600 border border-white/5 bg-white/[0.02] rounded-sm px-3 py-2" data-testid="risk-disclaimer">
    ⚠️ Trading futures involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results.
  </p>
);

/** Collapsible container for secondary tools — keeps the home screen clean. */
export const MoreTools = ({ children }) => {
  const [open, setOpen] = useState(false);
  return (
    <div id="more-tools" className="col-span-1 md:col-span-4 lg:col-span-12">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-3 py-2.5 bg-[#0D0D0F] border border-white/10 rounded-sm hover:bg-white/5 transition-colors"
        data-testid="more-tools-toggle"
      >
        <span className="flex items-center gap-2 text-xs font-black tracking-wider text-white">
          <LayoutGrid className="w-4 h-4 text-[#007AFF]" />
          MORE TOOLS
          <span className="text-[0.55rem] font-mono text-zinc-500 font-normal">NinjaTrader · TradingView · AI · Checklist · Vault · Health</span>
        </span>
        <ChevronDown className={`w-4 h-4 text-zinc-400 transition-transform duration-200 ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="grid grid-cols-1 md:grid-cols-4 lg:grid-cols-12 gap-3 md:gap-4 mt-3" data-testid="more-tools-content">
          {children}
        </div>
      )}
    </div>
  );
};

const NAV = [
  { label: "Terminal", target: "exec-top" },
  { label: "Chart", target: "chart-section" },
  { label: "Plans", target: "plans-section" },
  { label: "More", target: "more-tools" },
];

/** Mobile bottom navigation (replaces the floating wallet FAB). */
export const BottomNav = () => (
  <nav className="fixed bottom-0 inset-x-0 z-50 md:hidden bg-[#0A0A0A]/95 backdrop-blur-xl border-t border-white/10 grid grid-cols-4" data-testid="bottom-nav">
    {NAV.map((n) => (
      <button
        key={n.target}
        onClick={() => document.getElementById(n.target)?.scrollIntoView({ behavior: "smooth" })}
        className="py-3 text-[0.6rem] font-black tracking-wider text-zinc-400 hover:text-white active:text-[#007AFF] transition-colors"
        data-testid={`nav-${n.label.toLowerCase()}`}
      >
        {n.label}
      </button>
    ))}
  </nav>
);
