import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  TrendingUp, TrendingDown, Lock, DollarSign, Zap, Clock, X,
  AlertTriangle, Activity,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatPrice = (p) =>
  typeof p === "number" ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "0.00";

const ExecutionHub = ({ mnqPrice, safeMode }) => {
  const [trades, setTrades] = useState([]);
  const [sessionPnl, setSessionPnl] = useState(0);
  const [locked, setLocked] = useState(false);
  const [executing, setExecuting] = useState(null);
  const DAILY_LIMIT = -100;
  const SL_TICKS = 40;
  const TP_TICKS = 60;
  const TICK_VALUE = 0.25; // MNQ tick size
  const DOLLAR_PER_TICK = 0.50; // $0.50 per tick for MNQ

  const fetchTrades = useCallback(async () => {
    try {
      const res = await axios.get(`${API}/trades`);
      const todayTrades = res.data.filter(t => {
        const d = new Date(t.entry_date);
        const now = new Date();
        return d.toDateString() === now.toDateString();
      });
      setTrades(todayTrades);
      const closedPnl = todayTrades.filter(t => t.status === "closed").reduce((sum, t) => sum + (t.pnl || 0), 0);
      setSessionPnl(closedPnl);
      if (closedPnl <= DAILY_LIMIT) setLocked(true);
    } catch (e) { console.error(e); }
  }, []);

  useEffect(() => {
    fetchTrades();
    const interval = setInterval(fetchTrades, 3000);
    return () => clearInterval(interval);
  }, [fetchTrades]);

  // Reset lock at midnight
  useEffect(() => {
    const now = new Date();
    const midnight = new Date(now);
    midnight.setHours(24, 0, 0, 0);
    const msUntilMidnight = midnight - now;
    const timer = setTimeout(() => setLocked(false), msUntilMidnight);
    return () => clearTimeout(timer);
  }, []);

  const executePunch = async (side) => {
    if (locked) return;
    setExecuting(side);

    const price = mnqPrice || 18500;
    const slPoints = SL_TICKS * TICK_VALUE;
    const tpPoints = TP_TICKS * TICK_VALUE;

    let entry = price;
    let stopLoss, takeProfit;

    if (side === "long") {
      stopLoss = entry - slPoints;
      takeProfit = entry + tpPoints;
    } else {
      stopLoss = entry + slPoints;
      takeProfit = entry - tpPoints;
    }

    try {
      // Create trade
      const tradeRes = await axios.post(`${API}/trades`, {
        symbol: "MNQ",
        entry_price: entry,
        quantity: 1,
        side: side,
        notes: `SIM | SL: ${formatPrice(stopLoss)} | TP: ${formatPrice(takeProfit)} | ${safeMode ? "SAFE" : "PRO"} mode`,
      });

      // Also create a signal record
      await axios.post(`${API}/signals/test`);

      toast.success(
        `${side.toUpperCase()} PUNCH EXECUTED @ $${formatPrice(entry)}`,
        { className: side === "long" ? "alert-toast-bullish" : "alert-toast-bearish" }
      );

      // Simulate fill after delay
      setTimeout(async () => {
        // Random outcome weighted toward strategy win rate
        const rand = Math.random();
        let exitPrice, outcome;

        if (rand < 0.65) {
          // TP hit (65%)
          exitPrice = takeProfit;
          outcome = "closed";
        } else if (rand < 0.85) {
          // Partial win (20%)
          const partial = side === "long" ? entry + (tpPoints * 0.5) : entry - (tpPoints * 0.5);
          exitPrice = partial;
          outcome = "closed";
        } else {
          // SL hit (15%)
          exitPrice = stopLoss;
          outcome = "closed";
        }

        await axios.patch(`${API}/trades/${tradeRes.data.id}`, {
          exit_price: exitPrice,
          status: outcome,
        });

        await fetchTrades();
      }, 3000 + Math.random() * 5000);

      await fetchTrades();
    } catch (e) {
      toast.error("Execution failed");
    }

    setExecuting(null);
  };

  const openTrades = trades.filter(t => t.status === "open");
  const closedTrades = trades.filter(t => t.status === "closed").slice(0, 8);

  return (
    <div className="widget-panel col-span-1 md:col-span-4 lg:col-span-8" data-testid="execution-hub">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Zap className="w-4 h-4 text-[#FFCC00]" />
          EXECUTION HUB
        </h3>
        <div className="flex items-center gap-2">
          <span className={`text-[0.6rem] font-black px-2 py-0.5 rounded ${
            locked ? "bg-[#FF3B30] text-white" : safeMode ? "bg-[#34C759]/20 text-[#34C759]" : "bg-[#FF3B30]/20 text-[#FF3B30]"
          }`}>
            {locked ? "LOCKED" : safeMode ? "SAFE MODE" : "PRO MODE"}
          </span>
          <span className="text-[0.6rem] font-mono text-zinc-500">MNQ ${formatPrice(mnqPrice)}</span>
        </div>
      </div>
      <div className="widget-content">
        {/* BUY / SELL BUTTONS */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <button
            onClick={() => executePunch("long")}
            disabled={locked || executing === "long"}
            className={`relative p-4 rounded-sm font-black text-lg transition-all active:scale-95 ${
              locked
                ? "bg-zinc-800 text-zinc-600 cursor-not-allowed"
                : "bg-[#34C759] text-black hover:bg-[#2DB84E] hover:shadow-[0_0_30px_rgba(52,199,89,0.3)]"
            }`}
            data-testid="buy-punch-btn"
          >
            {executing === "long" ? (
              <span className="flex items-center justify-center gap-2"><Activity className="w-5 h-5 animate-spin" /> FILLING...</span>
            ) : (
              <span className="flex items-center justify-center gap-2"><TrendingUp className="w-6 h-6" /> BUY PUNCH</span>
            )}
            {!locked && safeMode && (
              <span className="block text-[0.6rem] font-normal mt-1 opacity-70">SL: 40 ticks | TP: 60 ticks</span>
            )}
          </button>
          <button
            onClick={() => executePunch("short")}
            disabled={locked || executing === "short"}
            className={`relative p-4 rounded-sm font-black text-lg transition-all active:scale-95 ${
              locked
                ? "bg-zinc-800 text-zinc-600 cursor-not-allowed"
                : "bg-[#FF3B30] text-white hover:bg-[#E5342A] hover:shadow-[0_0_30px_rgba(255,59,48,0.3)]"
            }`}
            data-testid="sell-punch-btn"
          >
            {executing === "short" ? (
              <span className="flex items-center justify-center gap-2"><Activity className="w-5 h-5 animate-spin" /> FILLING...</span>
            ) : (
              <span className="flex items-center justify-center gap-2"><TrendingDown className="w-6 h-6" /> SELL PUNCH</span>
            )}
            {!locked && safeMode && (
              <span className="block text-[0.6rem] font-normal mt-1 opacity-70">SL: 40 ticks | TP: 60 ticks</span>
            )}
          </button>
        </div>

        {/* Lock Message */}
        {locked && (
          <div className="p-3 bg-[#FF3B30]/10 border border-[#FF3B30]/40 rounded-sm flex items-center gap-2 mb-4">
            <Lock className="w-5 h-5 text-[#FF3B30]" />
            <div>
              <span className="text-sm font-bold text-[#FF3B30]">DAILY LOSS LIMIT REACHED</span>
              <span className="block text-[0.6rem] text-zinc-500">Execution disabled. Resets next trading day.</span>
            </div>
          </div>
        )}

        {/* Session Stats Bar */}
        <div className="grid grid-cols-4 gap-2 mb-3">
          <div className="p-2 bg-[#0A0A0A] border border-white/5 rounded-sm text-center">
            <span className="text-[0.5rem] text-zinc-600 uppercase block">Session P&L</span>
            <span className={`text-base font-mono font-black ${sessionPnl >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}
              style={{ textShadow: `0 0 10px ${sessionPnl >= 0 ? "#34C75980" : "#FF3B3080"}` }}
              data-testid="exec-session-pnl"
            >
              {sessionPnl >= 0 ? "+" : ""}${formatPrice(sessionPnl)}
            </span>
          </div>
          <div className="p-2 bg-[#0A0A0A] border border-white/5 rounded-sm text-center">
            <span className="text-[0.5rem] text-zinc-600 uppercase block">Open</span>
            <span className="text-base font-mono font-bold text-[#007AFF]">{openTrades.length}</span>
          </div>
          <div className="p-2 bg-[#0A0A0A] border border-white/5 rounded-sm text-center">
            <span className="text-[0.5rem] text-zinc-600 uppercase block">Closed</span>
            <span className="text-base font-mono font-bold text-white">{closedTrades.length}</span>
          </div>
          <div className="p-2 bg-[#0A0A0A] border border-white/5 rounded-sm text-center">
            <span className="text-[0.5rem] text-zinc-600 uppercase block">Limit</span>
            <span className="text-base font-mono font-bold text-[#FFCC00]">$100</span>
          </div>
        </div>

        {/* Active Trades */}
        {openTrades.length > 0 && (
          <div className="mb-3">
            <span className="text-[0.55rem] font-bold uppercase tracking-wider text-zinc-500 block mb-1.5">Active Positions</span>
            <div className="space-y-1">
              {openTrades.map(t => (
                <div key={t.id} className={`flex items-center justify-between p-2 rounded-sm border animate-pulse ${
                  t.side === "long" ? "bg-[#34C759]/5 border-[#34C759]/20" : "bg-[#FF3B30]/5 border-[#FF3B30]/20"
                }`} data-testid={`active-trade-${t.id}`}>
                  <div className="flex items-center gap-2">
                    {t.side === "long" ? <TrendingUp className="w-3 h-3 text-[#34C759]" /> : <TrendingDown className="w-3 h-3 text-[#FF3B30]" />}
                    <span className="text-xs font-bold text-white">MNQ {t.side.toUpperCase()}</span>
                  </div>
                  <span className="text-xs font-mono text-zinc-400">${formatPrice(t.entry_price)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Trade History */}
        {closedTrades.length > 0 && (
          <div>
            <span className="text-[0.55rem] font-bold uppercase tracking-wider text-zinc-500 block mb-1.5">Execution Log</span>
            <div className="space-y-1 max-h-[140px] overflow-y-auto">
              {closedTrades.map(t => (
                <div key={t.id} className="flex items-center justify-between p-1.5 bg-white/[0.02] rounded-sm text-xs" data-testid={`trade-log-${t.id}`}>
                  <div className="flex items-center gap-2">
                    {t.side === "long" ? <TrendingUp className="w-3 h-3 text-[#34C759]" /> : <TrendingDown className="w-3 h-3 text-[#FF3B30]" />}
                    <span className="font-mono text-zinc-400">{t.side.toUpperCase()}</span>
                    <span className="font-mono text-zinc-600">${formatPrice(t.entry_price)}</span>
                    <span className="text-zinc-600">→</span>
                    <span className="font-mono text-zinc-400">${formatPrice(t.exit_price)}</span>
                  </div>
                  <span className={`font-mono font-bold ${(t.pnl || 0) >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}
                    style={{ textShadow: `0 0 6px ${(t.pnl || 0) >= 0 ? "#34C75960" : "#FF3B3060"}` }}
                  >
                    {(t.pnl || 0) >= 0 ? "+" : ""}${formatPrice(t.pnl || 0)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ExecutionHub;
