import React, { useState } from "react";
import { toast } from "sonner";
import { Play, Monitor, Activity, TrendingUp, BarChart3 } from "lucide-react";

const SimulationTemple = () => {
  const [simActive, setSimActive] = useState(false);
  const [balance, setBalance] = useState(100000);

  const launchSim = () => {
    setSimActive(true);
    setBalance(100000);
    toast.success("100K Simulation LAUNCHED — MNQ Trinity loaded");
  };

  return (
    <div className="widget-panel col-span-1 md:col-span-4 lg:col-span-4" data-testid="simulation-temple">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Monitor className="w-4 h-4 text-[#007AFF]" />
          SIMULATION TEMPLE
        </h3>
        {simActive && (
          <span className="text-[0.6rem] font-black px-2 py-0.5 rounded bg-[#007AFF]/20 text-[#007AFF] flex items-center gap-1">
            <span className="w-1.5 h-1.5 bg-[#007AFF] rounded-full animate-pulse" /> SIM ACTIVE
          </span>
        )}
      </div>
      <div className="widget-content">
        {!simActive ? (
          <div className="text-center py-6">
            <div className="w-16 h-16 mx-auto mb-4 rounded-sm bg-[#007AFF]/10 border border-[#007AFF]/30 flex items-center justify-center">
              <Play className="w-8 h-8 text-[#007AFF]" />
            </div>
            <h4 className="text-lg font-black text-white mb-2">Practice Before You Punch</h4>
            <p className="text-xs text-zinc-500 max-w-xs mx-auto mb-4">
              Launch a $100K simulation with the MNQ Trinity pre-loaded: 21 EMA, 200 EMA, and VWAP.
            </p>
            <button
              onClick={launchSim}
              className="px-6 py-3 bg-[#007AFF] text-white font-black text-sm rounded-sm hover:bg-[#3395FF] transition-all active:scale-95 w-full max-w-xs"
              data-testid="launch-sim-btn"
            >
              Launch 100K Sim
            </button>
          </div>
        ) : (
          <div>
            {/* Sim Balance */}
            <div className="text-center p-4 bg-[#007AFF]/5 border border-[#007AFF]/30 rounded-sm mb-3">
              <span className="text-[0.6rem] text-zinc-500 uppercase tracking-wider block mb-1">Sim Balance</span>
              <span className="text-3xl font-mono font-bold text-[#007AFF]">
                ${balance.toLocaleString()}
              </span>
            </div>

            {/* MNQ Trinity */}
            <span className="text-[0.6rem] font-bold uppercase tracking-wider text-zinc-500 block mb-2">MNQ Trinity — Auto-Loaded</span>
            <div className="space-y-1.5">
              {[
                { name: "21 EMA", desc: "Navigate the Water", color: "#34C759", icon: TrendingUp },
                { name: "200 EMA", desc: "Follow the Roof", color: "#FFCC00", icon: BarChart3 },
                { name: "VWAP", desc: "Institutional Level", color: "#007AFF", icon: Activity },
              ].map((study) => (
                <div key={study.name} className="flex items-center justify-between p-2 bg-white/[0.03] rounded-sm border border-white/5">
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full" style={{ backgroundColor: study.color }} />
                    <span className="text-xs font-bold text-white">{study.name}</span>
                  </div>
                  <span className="text-[0.6rem] text-zinc-500">{study.desc}</span>
                </div>
              ))}
            </div>

            <button
              onClick={() => { setSimActive(false); toast("Simulation ended"); }}
              className="w-full mt-3 py-2 bg-white/10 text-zinc-400 text-xs rounded-sm hover:bg-white/20 transition-colors"
              data-testid="end-sim-btn"
            >
              End Simulation
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default SimulationTemple;
