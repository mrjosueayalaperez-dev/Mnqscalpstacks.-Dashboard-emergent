import React from "react";
import { BarChart3, RefreshCw, AlertTriangle, TrendingUp, TrendingDown } from "lucide-react";
import { formatPrice } from "@/lib/format";

export const MNQTracker = ({ data, loading }) => {
  const isPositive = data?.change >= 0;

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="mnq-tracker">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-[#007AFF]" />
          MNQ SCALP PUNCH
        </h3>
        <span className="text-xs text-zinc-500">MNQ Only</span>
      </div>
      <div className="widget-content">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <RefreshCw className="w-6 h-6 text-zinc-500 animate-spin" />
          </div>
        ) : (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="stat-box">
              <span className="stat-label">Price</span>
              <span
                className={`stat-value ${
                  isPositive ? "text-[#34C759] glow-green" : "text-[#FF3B30] glow-red"
                }`}
                data-testid="mnq-price"
              >
                {formatPrice(data?.price)}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Change</span>
              <span
                className={`stat-value text-lg ${
                  isPositive ? "text-[#34C759]" : "text-[#FF3B30]"
                }`}
              >
                {isPositive ? "+" : ""}
                {formatPrice(data?.change)} ({data?.change_percent || "0"}%)
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">VWAP</span>
              <span className="stat-value text-lg text-[#007AFF]">
                {formatPrice(data?.vwap)}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">RSI (14)</span>
              <span
                className={`stat-value text-lg ${
                  data?.rsi > 70
                    ? "text-[#FF3B30]"
                    : data?.rsi < 30
                    ? "text-[#34C759]"
                    : "text-white"
                }`}
              >
                {data?.rsi?.toFixed(1) || "50.0"}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">EMA 21 Spine</span>
              <span className="stat-value text-lg text-white">{formatPrice(data?.ema21)}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Close</span>
              <span className="stat-value text-lg">{formatPrice(data?.close)}</span>
            </div>
            <div className="stat-box">
              <span className="stat-label">High</span>
              <span className="stat-value text-lg text-[#34C759]">
                {formatPrice(data?.high)}
              </span>
            </div>
            <div className="stat-box">
              <span className="stat-label">Low</span>
              <span className="stat-value text-lg text-[#FF3B30]">
                {formatPrice(data?.low)}
              </span>
            </div>
          </div>
        )}
        {/* Signal Indicator */}
        {data && (
          <div className="mt-4 space-y-2">
            {/* Resistance Zone Warning */}
            {data?.in_resistance && data?.resistance_zones?.[0] && (
              <div className="p-2 bg-[#FF3B30]/10 border border-[#FF3B30]/30 rounded-sm flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#FF3B30]" />
                <span className="text-xs text-[#FF3B30] font-bold">RESISTANCE ZONE: {data?.resistance_zones?.[0]}</span>
              </div>
            )}
            <div className="p-3 bg-white/5 rounded-sm border border-white/10">
              <div className="flex items-center justify-between">
                <span className="text-xs uppercase tracking-wider text-zinc-500">
                  Scalp Punch Signal
                </span>
                {data?.close > data?.ema21 && data?.close > data?.vwap ? (
                  <span className="flex items-center gap-2 text-[#34C759] text-sm font-bold">
                    <TrendingUp className="w-4 h-4" /> BUY PUNCH
                  </span>
                ) : data?.close < data?.ema21 && data?.close < data?.vwap ? (
                  <span className="flex items-center gap-2 text-[#FF3B30] text-sm font-bold">
                    <TrendingDown className="w-4 h-4" /> SELL PUNCH
                  </span>
                ) : (
                  <span className="flex items-center gap-2 text-[#FFCC00] text-sm font-bold">
                    <AlertTriangle className="w-4 h-4" /> NO PUNCH — WAIT
                  </span>
                )}
              </div>
            </div>
            {/* Data Source */}
            <div className="flex items-center justify-between text-[0.6rem] text-zinc-600 px-1">
              <span>
                {data?.data_source === "mock" ? "MOCK DATA" :
                 data?.data_source === "qqq_proxy" ? "QQQ PROXY" : "LIVE MNQ"}
              </span>
              <span className={data?.wave_valid ? "text-[#34C759]" : "text-[#FF3B30]"}>
                Wave: {data?.wave_valid ? "VALID" : "INVALID"}
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
