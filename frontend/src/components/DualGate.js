import React, { useState } from "react";
import { toast } from "sonner";
import {
  Shield, ShieldOff, Lock, Unlock, Zap, AlertTriangle, ToggleLeft, ToggleRight,
} from "lucide-react";

// ============ DUAL-GATE EXECUTION ============
const DualGate = () => {
  const [safeMode, setSafeMode] = useState(true);
  const [proConfirm, setProConfirm] = useState(false);

  const togglePro = () => {
    if (safeMode) {
      setProConfirm(true);
    } else {
      setSafeMode(true);
      setProConfirm(false);
      toast.success("Safe Mode ENGAGED — Brackets Active");
    }
  };

  const confirmPro = () => {
    setSafeMode(false);
    setProConfirm(false);
    toast("Pro Mode ACTIVATED — All brackets removed", { className: "alert-toast-bearish" });
  };

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="dual-gate">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          {safeMode ? <Shield className="w-4 h-4 text-[#34C759]" /> : <ShieldOff className="w-4 h-4 text-[#FF3B30]" />}
          DUAL-GATE EXECUTION
        </h3>
        <span className={`text-[0.6rem] font-black px-2 py-0.5 rounded ${safeMode ? "bg-[#34C759]/20 text-[#34C759]" : "bg-[#FF3B30]/20 text-[#FF3B30]"}`}>
          {safeMode ? "SAFE" : "PRO"}
        </span>
      </div>
      <div className="widget-content">
        {/* Safety Gate */}
        <div className={`p-3 rounded-sm border mb-3 ${safeMode ? "bg-[#34C759]/5 border-[#34C759]/30" : "bg-white/5 border-white/10 opacity-50"}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Lock className="w-4 h-4 text-[#34C759]" />
              <span className="text-sm font-bold text-white">Safety Gate</span>
            </div>
            <span className={`text-[0.6rem] font-black ${safeMode ? "text-[#34C759]" : "text-zinc-600"}`}>
              {safeMode ? "ACTIVE" : "OFF"}
            </span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-2 bg-white/5 rounded-sm">
              <span className="text-[0.55rem] text-zinc-500 block">Stop Loss</span>
              <span className="text-sm font-mono font-bold text-[#FF3B30]">40 ticks</span>
            </div>
            <div className="p-2 bg-white/5 rounded-sm">
              <span className="text-[0.55rem] text-zinc-500 block">Take Profit</span>
              <span className="text-sm font-mono font-bold text-[#34C759]">60 ticks</span>
            </div>
            <div className="p-2 bg-white/5 rounded-sm">
              <span className="text-[0.55rem] text-zinc-500 block">Max Loss</span>
              <span className="text-sm font-mono font-bold text-[#FFCC00]">$100</span>
            </div>
          </div>
        </div>

        {/* Pro Toggle */}
        <div className={`p-3 rounded-sm border ${!safeMode ? "bg-[#FF3B30]/5 border-[#FF3B30]/30" : "bg-white/5 border-white/10"}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Unlock className="w-4 h-4 text-zinc-400" />
              <div>
                <span className="text-sm font-bold text-white block">Pro Toggle</span>
                <span className="text-[0.55rem] text-zinc-500">Removes all safety brackets</span>
              </div>
            </div>
            <button onClick={togglePro} className="transition-colors" data-testid="pro-toggle">
              {!safeMode ? <ToggleRight className="w-8 h-8 text-[#FF3B30]" /> : <ToggleLeft className="w-8 h-8 text-zinc-600" />}
            </button>
          </div>
        </div>

        {/* Pro Confirmation Modal */}
        {proConfirm && (
          <div className="mt-3 p-3 bg-[#FF3B30]/10 border border-[#FF3B30]/40 rounded-sm">
            <div className="flex items-center gap-2 mb-2">
              <AlertTriangle className="w-4 h-4 text-[#FF3B30]" />
              <span className="text-xs font-bold text-[#FF3B30]">WARNING: Raw Market Access</span>
            </div>
            <p className="text-[0.65rem] text-zinc-400 mb-2">This removes all safety brackets. Only for traders comfortable in the water.</p>
            <div className="flex gap-2">
              <button onClick={confirmPro} className="flex-1 py-1.5 bg-[#FF3B30] text-white text-xs font-bold rounded-sm hover:bg-[#FF3B30]/80" data-testid="confirm-pro">
                Confirm Pro Mode
              </button>
              <button onClick={() => setProConfirm(false)} className="flex-1 py-1.5 bg-white/10 text-zinc-400 text-xs rounded-sm hover:bg-white/20">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default DualGate;
