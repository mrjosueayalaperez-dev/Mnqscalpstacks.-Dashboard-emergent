import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import {
  Zap, TrendingUp, TrendingDown, ToggleLeft, ToggleRight, Radio,
  Activity, AlertTriangle, Clock, Target,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatPrice = (p) =>
  typeof p === "number" ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "0.00";

const AutoSignalEngine = ({ mnqData, onAutoExecute }) => {
  const [autoMode, setAutoMode] = useState(false);
  const [signals, setSignals] = useState([]);
  const [lastCheck, setLastCheck] = useState(null);

  const evaluateSignal = useCallback(() => {
    if (!mnqData) return null;

    const price = mnqData.close || mnqData.price || 0;
    const ema21 = mnqData.ema21 || 0;
    const vwap = mnqData.vwap || 0;
    const rsi = mnqData.rsi || 50;
    const isGreenCandle = (mnqData.close || 0) > (mnqData.open || mnqData.price || 0);

    // BUY signal rules
    const buyAboveEma = price > ema21;
    const buyAboveVwap = price > vwap;
    const buyRsi = rsi > 55;
    const buyCandle = isGreenCandle;
    const buyScore = [buyAboveEma, buyAboveVwap, buyRsi].filter(Boolean).length;
    const buySignal = buyScore >= 2 && buyCandle;

    // SELL signal rules
    const sellBelowEma = price < ema21;
    const sellBelowVwap = price < vwap;
    const sellRsi = rsi < 45;
    const sellCandle = !isGreenCandle;
    const sellScore = [sellBelowEma, sellBelowVwap, sellRsi].filter(Boolean).length;
    const sellSignal = sellScore >= 2 && sellCandle;

    if (buySignal) {
      return {
        id: Date.now().toString(),
        type: "BUY",
        entry: price,
        stopLoss: price - (40 * 0.25),
        takeProfit: price + (60 * 0.25),
        timestamp: new Date().toLocaleTimeString(),
        score: buyScore,
        confidence: buyScore === 3 ? "HIGH" : "MEDIUM",
        active: true,
        components: { ema21: buyAboveEma, vwap: buyAboveVwap, rsi: buyRsi, candle: buyCandle },
      };
    } else if (sellSignal) {
      return {
        id: Date.now().toString(),
        type: "SELL",
        entry: price,
        stopLoss: price + (40 * 0.25),
        takeProfit: price - (60 * 0.25),
        timestamp: new Date().toLocaleTimeString(),
        score: sellScore,
        confidence: sellScore === 3 ? "HIGH" : "MEDIUM",
        active: true,
        components: { ema21: sellBelowEma, vwap: sellBelowVwap, rsi: sellRsi, candle: sellCandle },
      };
    }
    return null;
  }, [mnqData]);

  // Auto-evaluate every 5 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      const signal = evaluateSignal();
      setLastCheck(new Date().toLocaleTimeString());

      if (signal) {
        // Prevent duplicate signals within 30 seconds
        const recent = signals[0];
        if (recent && (Date.now() - parseInt(recent.id)) < 30000 && recent.type === signal.type) return;

        setSignals(prev => [signal, ...prev].slice(0, 20));

        if (autoMode && onAutoExecute) {
          onAutoExecute(signal.type === "BUY" ? "long" : "short");
          toast(`AUTO ${signal.type} @ $${formatPrice(signal.entry)}`, {
            className: signal.type === "BUY" ? "alert-toast-bullish" : "alert-toast-bearish",
          });
        }
      }
    }, 5000);

    return () => clearInterval(interval);
  }, [evaluateSignal, autoMode, onAutoExecute, signals]);

  return (
    <div className="widget-panel col-span-1 md:col-span-4 lg:col-span-6" data-testid="auto-signal-engine">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <Target className="w-4 h-4 text-[#FFCC00]" />
          AUTO SIGNAL ENGINE
        </h3>
        <div className="flex items-center gap-2">
          {lastCheck && <span className="text-[0.55rem] text-zinc-600 font-mono">{lastCheck}</span>}
          <span className={`text-[0.6rem] font-black px-2 py-0.5 rounded ${
            autoMode ? "bg-[#34C759] text-black animate-pulse" : "bg-white/10 text-zinc-500"
          }`}>
            {autoMode ? "AUTO ON" : "MANUAL"}
          </span>
        </div>
      </div>
      <div className="widget-content">
        {/* Auto Execution Toggle */}
        <div className={`flex items-center justify-between p-2.5 rounded-sm border mb-3 transition-all ${
          autoMode ? "bg-[#34C759]/5 border-[#34C759]/30" : "bg-white/5 border-white/10"
        }`}>
          <div className="flex items-center gap-2">
            <Radio className={`w-4 h-4 ${autoMode ? "text-[#34C759] animate-pulse" : "text-zinc-600"}`} />
            <div>
              <span className="text-xs font-bold text-white block">Auto Execution Mode</span>
              <span className="text-[0.55rem] text-zinc-500">{autoMode ? "Signals auto-trade when fired" : "Manual BUY/SELL only"}</span>
            </div>
          </div>
          <button onClick={() => setAutoMode(!autoMode)} data-testid="auto-mode-toggle">
            {autoMode ? <ToggleRight className="w-7 h-7 text-[#34C759]" /> : <ToggleLeft className="w-7 h-7 text-zinc-600" />}
          </button>
        </div>

        {/* Signal Feed */}
        <div className="space-y-1.5 max-h-[250px] overflow-y-auto">
          {signals.length === 0 ? (
            <div className="text-center py-6 text-zinc-600">
              <Target className="w-6 h-6 mx-auto mb-2 opacity-40" />
              <p className="text-xs">Scanning for signals...</p>
              <p className="text-[0.55rem] mt-1">EMA 21 + VWAP + RSI confluence</p>
            </div>
          ) : (
            signals.map((sig) => (
              <div
                key={sig.id}
                className={`p-2.5 rounded-sm border transition-all ${
                  sig.type === "BUY"
                    ? "bg-[#34C759]/5 border-[#34C759]/20"
                    : "bg-[#FF3B30]/5 border-[#FF3B30]/20"
                }`}
                data-testid={`auto-signal-${sig.id}`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <div className="flex items-center gap-2">
                    {sig.type === "BUY" ? (
                      <TrendingUp className="w-4 h-4 text-[#34C759]" />
                    ) : (
                      <TrendingDown className="w-4 h-4 text-[#FF3B30]" />
                    )}
                    <span className={`text-xs font-black ${sig.type === "BUY" ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                      {sig.type} SIGNAL
                    </span>
                    <span className={`text-[0.5rem] px-1.5 py-0.5 rounded font-bold ${
                      sig.confidence === "HIGH" ? "bg-[#34C759]/20 text-[#34C759]" : "bg-[#FFCC00]/20 text-[#FFCC00]"
                    }`}>
                      {sig.confidence} ({sig.score}/3)
                    </span>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <Clock className="w-3 h-3 text-zinc-600" />
                    <span className="text-[0.55rem] text-zinc-500 font-mono">{sig.timestamp}</span>
                  </div>
                </div>
                <div className="grid grid-cols-3 gap-2 text-[0.6rem] font-mono">
                  <div>
                    <span className="text-zinc-600 block">Entry</span>
                    <span className="text-white">${formatPrice(sig.entry)}</span>
                  </div>
                  <div>
                    <span className="text-zinc-600 block">SL (40t)</span>
                    <span className="text-[#FF3B30]">${formatPrice(sig.stopLoss)}</span>
                  </div>
                  <div>
                    <span className="text-zinc-600 block">TP (60t)</span>
                    <span className="text-[#34C759]">${formatPrice(sig.takeProfit)}</span>
                  </div>
                </div>
                {/* Component dots */}
                <div className="flex gap-1.5 mt-1.5">
                  {Object.entries(sig.components).map(([k, v]) => (
                    <span key={k} className={`text-[0.5rem] px-1 py-0.5 rounded ${
                      v ? "bg-[#34C759]/10 text-[#34C759]" : "bg-white/5 text-zinc-600"
                    }`}>
                      {k}
                    </span>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};

export default AutoSignalEngine;
