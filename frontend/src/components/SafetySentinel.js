import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Shield, ShieldOff, AlertTriangle, DollarSign, TrendingUp, TrendingDown,
  Lock, Activity, Zap, Radio,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatPrice = (p) =>
  typeof p === "number" ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "0.00";

const DAILY_LIMIT = -100;

const SafetySentinel = () => {
  const [trades, setTrades] = useState([]);
  const [stats, setStats] = useState({ total_pnl: 0 });
  const [locked, setLocked] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [tradesRes, statsRes] = await Promise.all([
        axios.get(`${API}/trades?status=open`),
        axios.get(`${API}/trades/stats`),
      ]);
      setTrades(tradesRes.data);
      setStats(statsRes.data);

      // Auto-lock at -$100
      if (statsRes.data.total_pnl <= DAILY_LIMIT) {
        setLocked(true);
      }
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const sessionPnl = stats.total_pnl || 0;
  const pnlPercent = Math.min(Math.abs(sessionPnl) / Math.abs(DAILY_LIMIT) * 100, 100);
  const isNegative = sessionPnl < 0;

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="safety-sentinel">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Shield className="w-4 h-4 text-[#FF3B30]" />
          SAFETY SENTINEL
        </h3>
        <span className={`text-[0.6rem] font-bold px-2 py-0.5 rounded ${
          locked ? "bg-[#FF3B30] text-white" : "bg-[#34C759]/20 text-[#34C759]"
        }`}>
          {locked ? "LOCKED" : "ACTIVE"}
        </span>
      </div>
      <div className="widget-content">
        {/* Session P&L — The Main Number */}
        <div className={`text-center p-4 rounded-sm mb-3 border ${
          locked ? "bg-[#FF3B30]/10 border-[#FF3B30]/40" :
          isNegative ? "bg-[#FF3B30]/5 border-[#FF3B30]/20" :
          "bg-[#34C759]/5 border-[#34C759]/20"
        }`}>
          <span className="text-[0.6rem] font-bold uppercase tracking-[0.15em] text-zinc-500 block mb-1">
            Session P&L
          </span>
          <span className={`text-3xl md:text-4xl font-mono font-black ${
            locked ? "text-[#FF3B30] glow-red" :
            isNegative ? "text-[#FF3B30]" : "text-[#34C759] glow-green"
          }`} data-testid="session-pnl">
            {sessionPnl >= 0 ? "+" : ""}${formatPrice(sessionPnl)}
          </span>
          {locked && (
            <div className="flex items-center justify-center gap-2 mt-2 text-[#FF3B30]">
              <Lock className="w-4 h-4" />
              <span className="text-xs font-bold">DAILY LIMIT REACHED — SYSTEM LOCKED</span>
            </div>
          )}
        </div>

        {/* $100 Limit Bar */}
        <div className="mb-3">
          <div className="flex justify-between text-[0.6rem] text-zinc-500 mb-1">
            <span>ATM $100 Rule</span>
            <span className="font-mono">${Math.abs(sessionPnl).toFixed(2)} / $100.00</span>
          </div>
          <div className="h-2 bg-white/10 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                pnlPercent >= 80 ? "bg-[#FF3B30]" :
                pnlPercent >= 50 ? "bg-[#FFCC00]" : "bg-[#34C759]"
              }`}
              style={{ width: `${isNegative ? pnlPercent : 0}%` }}
            />
          </div>
        </div>

        {/* Quick Stats */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div className="stat-box">
            <span className="stat-label">Win Rate</span>
            <span className={`text-lg font-mono font-bold ${stats.win_rate >= 50 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
              {stats.win_rate || 0}%
            </span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Trades</span>
            <span className="text-lg font-mono font-bold text-white">{stats.total_trades || 0}</span>
          </div>
          <div className="stat-box">
            <span className="stat-label">Open</span>
            <span className="text-lg font-mono font-bold text-[#007AFF]">{trades.length}</span>
          </div>
        </div>

        {/* Open Positions */}
        {trades.length > 0 && (
          <div>
            <span className="text-[0.6rem] font-bold uppercase tracking-wider text-zinc-500 block mb-2">Open Positions</span>
            <div className="space-y-1.5">
              {trades.slice(0, 5).map((t) => (
                <div key={t.id} className="flex items-center justify-between p-2 bg-white/[0.03] rounded-sm" data-testid={`open-trade-${t.id}`}>
                  <div className="flex items-center gap-2">
                    {t.side === "long" ? <TrendingUp className="w-3 h-3 text-[#34C759]" /> : <TrendingDown className="w-3 h-3 text-[#FF3B30]" />}
                    <span className="text-xs font-bold text-white">{t.symbol}</span>
                    <span className={`text-[0.55rem] px-1 py-0.5 rounded ${t.side === "long" ? "bg-[#34C759]/20 text-[#34C759]" : "bg-[#FF3B30]/20 text-[#FF3B30]"}`}>
                      {t.side.toUpperCase()}
                    </span>
                  </div>
                  <span className="text-xs font-mono text-zinc-400">${formatPrice(t.entry_price)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {trades.length === 0 && !locked && (
          <div className="text-center py-3 text-zinc-600 text-xs">
            <Shield className="w-5 h-5 mx-auto mb-1 opacity-40" />
            No open positions — Sentinel watching
          </div>
        )}
      </div>
    </div>
  );
};

export default SafetySentinel;
