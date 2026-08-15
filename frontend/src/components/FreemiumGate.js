import React from "react";
import { Crown, Star, Zap, Check, ExternalLink, Lock } from "lucide-react";

const FreemiumGate = ({ userPlan, onUpgrade }) => {
  const plan = userPlan || "free";

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-6" data-testid="freemium-gate">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Crown className="w-4 h-4 text-[#FFCC00]" />
          SUBSCRIPTION PLANS
        </h3>
        <span className={`text-[0.6rem] font-black px-2 py-0.5 rounded ${
          plan === "elite" ? "bg-[#34C759]/20 text-[#34C759]" :
          plan === "pro" ? "bg-[#FFCC00]/20 text-[#FFCC00]" :
          "bg-white/10 text-zinc-500"
        }`}>
          {plan.toUpperCase()}
        </span>
      </div>
      <div className="widget-content">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          {/* Free */}
          <div className={`p-3 rounded-sm border text-center ${plan === "free" ? "border-[#007AFF]/40 bg-[#007AFF]/5" : "border-white/5 bg-white/[0.02]"}`}>
            <Zap className="w-5 h-5 text-[#007AFF] mx-auto mb-1" />
            <span className="text-xs font-black text-white block">Free</span>
            <span className="text-lg font-mono font-bold text-white block mb-2">$0</span>
            <ul className="text-[0.55rem] text-zinc-400 space-y-1 text-left mb-2">
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#007AFF] shrink-0" />Simulator access</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#007AFF] shrink-0" />Manual BUY/SELL</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#007AFF] shrink-0" />Last 3 signals</li>
              <li className="flex items-start gap-1 opacity-40"><Lock className="w-2.5 h-2.5 mt-0.5 shrink-0" />Ads shown</li>
            </ul>
            {plan === "free" && <span className="text-[0.55rem] text-[#007AFF] font-bold">CURRENT</span>}
          </div>

          {/* Pro */}
          <div className={`p-3 rounded-sm border text-center relative ${plan === "pro" ? "border-[#FFCC00]/40 bg-[#FFCC00]/5 ring-1 ring-[#FFCC00]/30" : "border-white/5 bg-white/[0.02]"}`}>
            <div className="absolute -top-2 left-1/2 -translate-x-1/2 px-2 py-0.5 bg-[#FFCC00] text-black text-[0.45rem] font-black rounded-sm">POPULAR</div>
            <Star className="w-5 h-5 text-[#FFCC00] mx-auto mb-1" />
            <span className="text-xs font-black text-white block">Pro</span>
            <span className="text-lg font-mono font-bold text-white block mb-2">$49<span className="text-[0.55rem] text-zinc-500">/mo</span></span>
            <ul className="text-[0.55rem] text-zinc-400 space-y-1 text-left mb-2">
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#FFCC00] shrink-0" />No ads</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#FFCC00] shrink-0" />Unlimited signals</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#FFCC00] shrink-0" />Discord alerts</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#FFCC00] shrink-0" />Analytics</li>
            </ul>
            {plan === "pro" ? (
              <span className="text-[0.55rem] text-[#FFCC00] font-bold">CURRENT</span>
            ) : (
              <a href="/performance" className="text-[0.55rem] text-[#FFCC00] font-bold hover:underline">UPGRADE</a>
            )}
          </div>

          {/* Premium */}
          <div className={`p-3 rounded-sm border text-center ${plan === "premium" ? "border-[#BF5AF2]/40 bg-[#BF5AF2]/5" : "border-white/5 bg-white/[0.02]"}`} data-testid="tier-premium">
            <Star className="w-5 h-5 text-[#BF5AF2] mx-auto mb-1" />
            <span className="text-xs font-black text-white block">Premium</span>
            <span className="text-lg font-mono font-bold text-white block mb-2">$99.99<span className="text-[0.55rem] text-zinc-500">/mo</span></span>
            <ul className="text-[0.55rem] text-zinc-400 space-y-1 text-left mb-2">
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#BF5AF2] shrink-0" />Everything in Pro</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#BF5AF2] shrink-0" />Operator bracket presets</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#BF5AF2] shrink-0" />Live key-level alerts</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#BF5AF2] shrink-0" />Weekly performance report</li>
            </ul>
            {plan === "premium" ? (
              <span className="text-[0.55rem] text-[#BF5AF2] font-bold">CURRENT</span>
            ) : (
              <a href="/performance" className="text-[0.55rem] text-[#BF5AF2] font-bold hover:underline">UPGRADE</a>
            )}
          </div>

          {/* Elite */}
          <div className={`p-3 rounded-sm border text-center ${plan === "elite" ? "border-[#34C759]/40 bg-[#34C759]/5" : "border-white/5 bg-white/[0.02]"}`}>
            <Crown className="w-5 h-5 text-[#34C759] mx-auto mb-1" />
            <span className="text-xs font-black text-white block">Elite</span>
            <span className="text-lg font-mono font-bold text-white block mb-2">$149<span className="text-[0.55rem] text-zinc-500">/mo</span></span>
            <ul className="text-[0.55rem] text-zinc-400 space-y-1 text-left mb-2">
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#34C759] shrink-0" />Everything in Pro</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#34C759] shrink-0" />1-on-1 review</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#34C759] shrink-0" />Priority signals</li>
              <li className="flex items-start gap-1"><Check className="w-2.5 h-2.5 mt-0.5 text-[#34C759] shrink-0" />Webhook API</li>
            </ul>
            {plan === "elite" ? (
              <span className="text-[0.55rem] text-[#34C759] font-bold">CURRENT</span>
            ) : (
              <a href="/performance" className="text-[0.55rem] text-[#34C759] font-bold hover:underline">UPGRADE</a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

// Ad placement containers for Free tier
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
