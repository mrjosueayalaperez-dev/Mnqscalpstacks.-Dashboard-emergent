import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { Activity, TrendingUp, TrendingDown, BarChart3, Zap, Target } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatPrice = (p) =>
  typeof p === "number" ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "0.00";

const PerformanceEngine = () => {
  const [stats, setStats] = useState({});
  const [signalStats, setSignalStats] = useState({});
  const [mnqData, setMnqData] = useState(null);

  const fetchData = useCallback(async () => {
    try {
      const [tradeRes, sigRes, mnqRes] = await Promise.all([
        axios.get(`${API}/trades/stats`),
        axios.get(`${API}/signals/stats`),
        axios.get(`${API}/futures/mnq`),
      ]);
      setStats(tradeRes.data);
      setSignalStats(sigRes.data);
      setMnqData(mnqRes.data);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 8000);
    return () => clearInterval(interval);
  }, [fetchData]);

  // EMA Stack alignment
  const ema21 = mnqData?.ema21 || 0;
  const vwap = mnqData?.vwap || 0;
  const price = mnqData?.close || mnqData?.price || 0;
  const stackAligned = price > ema21 && price > vwap;
  const stackBearish = price < ema21 && price < vwap;

  const metrics = [
    { label: "Daily P&L", value: `${stats.total_pnl >= 0 ? "+" : ""}$${formatPrice(stats.total_pnl || 0)}`, color: (stats.total_pnl || 0) >= 0 ? "#34C759" : "#FF3B30", glow: true },
    { label: "Win Rate", value: `${stats.win_rate || 0}%`, color: (stats.win_rate || 0) >= 50 ? "#34C759" : "#FF3B30", glow: false },
    { label: "Avg Win", value: `+$${formatPrice(stats.avg_win || 0)}`, color: "#34C759", glow: false },
    { label: "Avg Loss", value: `$${formatPrice(stats.avg_loss || 0)}`, color: "#FF3B30", glow: false },
    { label: "Signals", value: signalStats.total_signals || 0, color: "#007AFF", glow: false },
    { label: "Sig Win%", value: `${signalStats.win_rate || 0}%`, color: (signalStats.win_rate || 0) >= 50 ? "#34C759" : "#FF3B30", glow: false },
  ];

  return (
    <div className="widget-panel col-span-1 md:col-span-4 lg:col-span-8" data-testid="performance-engine">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-[#007AFF]" />
          PERFORMANCE ENGINE
        </h3>
        {/* Stack Status */}
        <div className="flex items-center gap-2">
          <span className="text-[0.6rem] text-zinc-500">EMA STACK:</span>
          {stackAligned ? (
            <span className="flex items-center gap-1 text-[0.6rem] font-black text-[#34C759]">
              <TrendingUp className="w-3 h-3" /> ALIGNED
            </span>
          ) : stackBearish ? (
            <span className="flex items-center gap-1 text-[0.6rem] font-black text-[#FF3B30]">
              <TrendingDown className="w-3 h-3" /> INVERTED
            </span>
          ) : (
            <span className="flex items-center gap-1 text-[0.6rem] font-black text-[#FFCC00]">
              <Activity className="w-3 h-3" /> MIXED
            </span>
          )}
        </div>
      </div>
      <div className="widget-content">
        {/* Neon Readout Grid */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-2">
          {metrics.map((m) => (
            <div key={m.label} className="p-3 bg-[#0A0A0A] border border-white/5 rounded-sm text-center" data-testid={`perf-${m.label.toLowerCase().replace(/[\s%]/g, "-")}`}>
              <span className="text-[0.5rem] font-bold uppercase tracking-[0.2em] text-zinc-600 block mb-1">{m.label}</span>
              <span
                className="text-lg md:text-xl font-mono font-black block"
                style={{
                  color: m.color,
                  textShadow: m.glow ? `0 0 12px ${m.color}80` : "none",
                }}
              >
                {m.value}
              </span>
            </div>
          ))}
        </div>

        {/* System Health Bar */}
        <div className="mt-3 p-2.5 bg-[#0A0A0A] border border-white/5 rounded-sm flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-1.5">
              <div className={`w-2 h-2 rounded-full ${stackAligned ? "bg-[#34C759] animate-pulse" : stackBearish ? "bg-[#FF3B30]" : "bg-[#FFCC00]"}`} />
              <span className="text-[0.6rem] text-zinc-400">Stack Health</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Zap className="w-3 h-3 text-[#FFCC00]" />
              <span className="text-[0.6rem] text-zinc-400">Freq: {signalStats.signal_frequency_per_day || 0}/day</span>
            </div>
            <div className="flex items-center gap-1.5">
              <Target className="w-3 h-3 text-[#007AFF]" />
              <span className="text-[0.6rem] text-zinc-400">R:R {signalStats.avg_rr || 0}:1</span>
            </div>
          </div>
          <span className="text-[0.6rem] font-mono text-zinc-600">
            MNQ {formatPrice(price)}
          </span>
        </div>
      </div>
    </div>
  );
};

export default PerformanceEngine;
