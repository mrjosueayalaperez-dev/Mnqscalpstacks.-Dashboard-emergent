import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Zap, Activity, Radio, TrendingUp, TrendingDown, AlertTriangle,
  ToggleLeft, ToggleRight, Wifi, WifiOff, Gauge,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatPrice = (p) =>
  typeof p === "number" ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";

const HydroPilot = () => {
  const [mnqData, setMnqData] = useState(null);
  const [autoPilot, setAutoPilot] = useState(false);
  const [health, setHealth] = useState({});
  const [killSwitch, setKillSwitch] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [mnqRes, healthRes, killRes] = await Promise.all([
        axios.get(`${API}/futures/mnq`),
        axios.get(`${API}/signals/health`),
        axios.get(`${API}/signals/kill-switch`),
      ]);
      setMnqData(mnqRes.data);
      setHealth(healthRes.data);
      setKillSwitch(killRes.data.kill_switch);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const toggleAutoPilot = async () => {
    const newState = !autoPilot;
    setAutoPilot(newState);
    toast(newState ? "Hydro-Pilot ENGAGED" : "Hydro-Pilot DISENGAGED", {
      className: newState ? "alert-toast-bullish" : "alert-toast-bearish",
    });
  };

  // Study readings
  const price = mnqData?.close || mnqData?.price || 0;
  const ema21 = mnqData?.ema21 || 0;
  const vwap = mnqData?.vwap || 0;

  // Go/No-Go checks
  const ema21Go = price > ema21;
  const vwapGo = price > vwap;
  const allGo = ema21Go && vwapGo;

  // Signal direction
  const direction = allGo ? "LONG" : (!ema21Go && !vwapGo) ? "SHORT" : "NEUTRAL";

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="hydro-pilot">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Gauge className="w-4 h-4 text-[#007AFF]" />
          HYDRO-PILOT
        </h3>
        <span className="text-[0.6rem] text-zinc-500">MNQ ONLY</span>
      </div>
      <div className="widget-content">
        {/* Auto-Pilot Toggle */}
        <div className="flex items-center justify-between p-3 bg-white/5 rounded-sm border border-white/10 mb-3">
          <div className="flex items-center gap-2">
            <Radio className={`w-4 h-4 ${autoPilot ? "text-[#34C759] animate-pulse" : "text-zinc-600"}`} />
            <span className="text-sm font-bold text-white">Auto-Pilot</span>
          </div>
          <button
            onClick={toggleAutoPilot}
            className="transition-colors"
            data-testid="autopilot-toggle"
          >
            {autoPilot ? (
              <ToggleRight className="w-8 h-8 text-[#34C759]" />
            ) : (
              <ToggleLeft className="w-8 h-8 text-zinc-600" />
            )}
          </button>
        </div>

        {/* Go / No-Go Panel */}
        <div className="mb-3">
          <span className="text-[0.6rem] font-bold uppercase tracking-wider text-zinc-500 block mb-2">
            Study Status — Go / No-Go
          </span>
          <div className="space-y-1.5">
            {/* EMA 21 */}
            <div className={`flex items-center justify-between p-2.5 rounded-sm border ${
              ema21Go ? "bg-[#34C759]/5 border-[#34C759]/30" : "bg-[#FF3B30]/5 border-[#FF3B30]/30"
            }`} data-testid="ema21-status">
              <div className="flex items-center gap-2">
                <div className={`w-2.5 h-2.5 rounded-full ${ema21Go ? "bg-[#34C759]" : "bg-[#FF3B30]"}`} />
                <span className="text-xs font-bold text-white">EMA 21 Spine</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-zinc-400">{formatPrice(ema21)}</span>
                <span className={`text-xs font-black ${ema21Go ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                  {ema21Go ? "GO" : "NO-GO"}
                </span>
              </div>
            </div>

            {/* VWAP */}
            <div className={`flex items-center justify-between p-2.5 rounded-sm border ${
              vwapGo ? "bg-[#34C759]/5 border-[#34C759]/30" : "bg-[#FF3B30]/5 border-[#FF3B30]/30"
            }`} data-testid="vwap-status">
              <div className="flex items-center gap-2">
                <div className={`w-2.5 h-2.5 rounded-full ${vwapGo ? "bg-[#34C759]" : "bg-[#FF3B30]"}`} />
                <span className="text-xs font-bold text-white">Session VWAP</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-zinc-400">{formatPrice(vwap)}</span>
                <span className={`text-xs font-black ${vwapGo ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                  {vwapGo ? "GO" : "NO-GO"}
                </span>
              </div>
            </div>

            {/* Resistance */}
            <div className={`flex items-center justify-between p-2.5 rounded-sm border ${
              mnqData?.in_resistance ? "bg-[#FF3B30]/5 border-[#FF3B30]/30" : "bg-white/5 border-white/10"
            }`} data-testid="resistance-status">
              <div className="flex items-center gap-2">
                <div className={`w-2.5 h-2.5 rounded-full ${mnqData?.in_resistance ? "bg-[#FF3B30] animate-pulse" : "bg-zinc-600"}`} />
                <span className="text-xs font-bold text-white">Key Resistance</span>
              </div>
              <span className={`text-xs font-black ${mnqData?.in_resistance ? "text-[#FF3B30]" : "text-zinc-500"}`}>
                {mnqData?.in_resistance ? "BLOCKED" : "CLEAR"}
              </span>
            </div>
          </div>
        </div>

        {/* Direction Verdict */}
        <div className={`p-3 rounded-sm border text-center ${
          direction === "LONG" ? "bg-[#34C759]/10 border-[#34C759]/40" :
          direction === "SHORT" ? "bg-[#FF3B30]/10 border-[#FF3B30]/40" :
          "bg-[#FFCC00]/10 border-[#FFCC00]/40"
        }`} data-testid="direction-verdict">
          <span className="text-[0.6rem] text-zinc-500 uppercase tracking-wider block mb-1">Direction</span>
          <div className="flex items-center justify-center gap-2">
            {direction === "LONG" ? <TrendingUp className="w-5 h-5 text-[#34C759]" /> :
             direction === "SHORT" ? <TrendingDown className="w-5 h-5 text-[#FF3B30]" /> :
             <AlertTriangle className="w-5 h-5 text-[#FFCC00]" />}
            <span className={`text-xl font-black ${
              direction === "LONG" ? "text-[#34C759]" :
              direction === "SHORT" ? "text-[#FF3B30]" : "text-[#FFCC00]"
            }`}>
              {direction === "NEUTRAL" ? "WAIT" : direction}
            </span>
          </div>
        </div>

        {/* Connectivity */}
        <div className="flex items-center justify-between mt-3 text-[0.6rem] text-zinc-600 px-1">
          <span className="flex items-center gap-1">
            {health.discord_configured ? <Wifi className="w-3 h-3 text-[#34C759]" /> : <WifiOff className="w-3 h-3 text-[#FF3B30]" />}
            Discord: {health.discord_configured ? "LIVE" : "OFF"}
          </span>
          <span className="flex items-center gap-1">
            <Activity className="w-3 h-3" />
            Engine: {health.status?.toUpperCase() || "—"}
          </span>
          <span className={killSwitch ? "text-[#FF3B30]" : "text-zinc-600"}>
            Kill: {killSwitch ? "ON" : "OFF"}
          </span>
        </div>
      </div>
    </div>
  );
};

export default HydroPilot;
