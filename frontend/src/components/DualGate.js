import React, { useState } from "react";
import { toast } from "sonner";
import {
  Shield, ShieldOff, Lock, Unlock, AlertTriangle, ToggleLeft, ToggleRight,
} from "lucide-react";

const DualGate = ({ safeMode, onToggleSafe }) => {
  const [proConfirm, setProConfirm] = useState(false);

  const togglePro = () => {
    if (safeMode) {
      setProConfirm(true);
    } else {
      onToggleSafe(true);
      setProConfirm(false);
      toast.success("Safe Mode ENGAGED — Brackets Active");
    }
  };

  const confirmPro = () => {
    onToggleSafe(false);
    setProConfirm(false);
    toast("PRO MODE ACTIVATED — All brackets removed", { className: "alert-toast-bearish" });
  };

  return (
    <div className={`widget-panel col-span-1 md:col-span-2 lg:col-span-4 transition-all ${
      !safeMode ? "ring-1 ring-[#FF3B30]/50 shadow-[0_0_20px_rgba(255,59,48,0.15)]" : ""
    }`} data-testid="dual-gate">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          {safeMode ? <Shield className="w-4 h-4 text-[#34C759]" /> : <ShieldOff className="w-4 h-4 text-[#FF3B30]" />}
          DUAL-GATE
        </h3>
        <span className={`text-[0.6rem] font-black px-2 py-0.5 rounded ${safeMode ? "bg-[#34C759]/20 text-[#34C759]" : "bg-[#FF3B30] text-white animate-pulse"}`}>
          {safeMode ? "SAFE" : "PRO — BRACKETS OFF"}
        </span>
      </div>
      <div className="widget-content">
        {/* Safety Gate */}
        <div className={`p-3 rounded-sm border mb-3 ${safeMode ? "bg-[#34C759]/5 border-[#34C759]/30" : "bg-white/5 border-white/10 opacity-40"}`}>
          <div className="flex items-center gap-2 mb-2">
            <Lock className="w-4 h-4 text-[#34C759]" />
            <span className="text-sm font-bold text-white">Safety Gate</span>
          </div>
          <div className="grid grid-cols-3 gap-2 text-center">
            <div className="p-1.5 bg-white/5 rounded-sm">
              <span className="text-[0.5rem] text-zinc-500 block">SL</span>
              <span className="text-xs font-mono font-bold text-[#FF3B30]">40 tick</span>
            </div>
            <div className="p-1.5 bg-white/5 rounded-sm">
              <span className="text-[0.5rem] text-zinc-500 block">TP</span>
              <span className="text-xs font-mono font-bold text-[#34C759]">60 tick</span>
            </div>
            <div className="p-1.5 bg-white/5 rounded-sm">
              <span className="text-[0.5rem] text-zinc-500 block">Limit</span>
              <span className="text-xs font-mono font-bold text-[#FFCC00]">$100</span>
            </div>
          </div>
        </div>

        {/* Pro Toggle */}
        <div className={`p-3 rounded-sm border ${!safeMode ? "bg-[#FF3B30]/10 border-[#FF3B30]/40" : "bg-white/5 border-white/10"}`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Unlock className="w-4 h-4 text-zinc-400" />
              <span className="text-xs font-bold text-white">Pro Toggle</span>
            </div>
            <button onClick={togglePro} data-testid="pro-toggle">
              {!safeMode ? <ToggleRight className="w-7 h-7 text-[#FF3B30]" /> : <ToggleLeft className="w-7 h-7 text-zinc-600" />}
            </button>
          </div>
        </div>

        {proConfirm && (
          <div className="mt-2 p-2.5 bg-[#FF3B30]/10 border border-[#FF3B30]/40 rounded-sm">
            <div className="flex items-center gap-1.5 mb-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-[#FF3B30]" />
              <span className="text-[0.65rem] font-bold text-[#FF3B30]">Remove all safety brackets?</span>
            </div>
            <div className="flex gap-2">
              <button onClick={confirmPro} className="flex-1 py-1.5 bg-[#FF3B30] text-white text-[0.65rem] font-bold rounded-sm" data-testid="confirm-pro">
                Confirm Pro
              </button>
              <button onClick={() => setProConfirm(false)} className="flex-1 py-1.5 bg-white/10 text-zinc-400 text-[0.65rem] rounded-sm">
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
