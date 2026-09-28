import React from "react";
import { GraduationCap, Check } from "lucide-react";

/** Free-access banner — all features unlocked for everyone (subscriptions removed). */
const FreemiumGate = () => (
  <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-6" data-testid="freemium-gate">
    <div className="widget-header">
      <h3 className="flex items-center gap-2">
        <GraduationCap className="w-4 h-4 text-[#34C759]" />
        FREE ACCESS
      </h3>
      <span className="text-[0.6rem] font-black px-2 py-0.5 rounded bg-[#34C759]/20 text-[#34C759]">100% FREE</span>
    </div>
    <div className="widget-content">
      <p className="text-xs text-zinc-300 mb-2">
        MNQ Scalp Stacks is a <span className="text-[#34C759] font-bold">free learning service</span> — every tool is
        unlocked for everyone: live signals, AI copilot, charts, Discord alerts, and the Community Lab.
      </p>
      <ul className="grid grid-cols-2 gap-1.5">
        {["Real-time signals", "AI trade copilot", "Signal charts + levels", "Discord alerts", "Community Lab", "Practice journal"].map((f) => (
          <li key={f} className="flex items-start gap-1.5 text-[0.65rem] text-zinc-400">
            <Check className="w-3 h-3 mt-0.5 text-[#34C759] shrink-0" />{f}
          </li>
        ))}
      </ul>
      <a href="/community-lab" className="inline-block mt-3 px-3 py-1.5 bg-[#34C759] text-black text-[0.65rem] font-black rounded-sm hover:bg-[#2DB84E] transition-colors" data-testid="free-lab-link">
        OPEN THE FREE COMMUNITY LAB
      </a>
      <p className="mt-2 text-[0.55rem] text-zinc-600">Educational simulation only — not financial advice. Futures involve substantial risk of loss.</p>
    </div>
  </div>
);

// Ad placement containers (partner placeholders)
const AdBanner = ({ position }) => (
  <div className={`bg-[#121212] border border-white/5 rounded-sm p-2.5 text-center ${
    position === "top" ? "col-span-1 md:col-span-4 lg:col-span-12" :
    position === "sidebar" ? "col-span-1 md:col-span-2 lg:col-span-4" :
    "col-span-1 md:col-span-4 lg:col-span-12"
  }`} data-testid={`ad-${position}`}>
    <div className="flex items-center justify-center gap-2 py-1.5 opacity-40">
      <span className="text-[0.5rem] uppercase tracking-wider text-zinc-600">
        {position === "top" ? "Sponsored Market Tools" :
         position === "sidebar" ? "Broker Partner" :
         "Trading Education Partner"}
      </span>
    </div>
  </div>
);

export { FreemiumGate, AdBanner };
export default FreemiumGate;
