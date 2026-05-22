import React from "react";
import { Radio } from "lucide-react";

export default function SignalPanel({ mnqData }) {
  const price = mnqData?.close || mnqData?.price || 0;
  const ema21 = mnqData?.ema21 || 0;
  const vwap = mnqData?.vwap || 0;
  const rsi = mnqData?.rsi || 50;

  const above = price > ema21 && price > vwap;
  const below = price < ema21 && price < vwap;
  const bias = above ? "LONG" : below ? "SHORT" : "NEUTRAL";
  const biasColor = bias === "LONG" ? "#34C759" : bias === "SHORT" ? "#FF3B30" : "#FFCC00";

  // Confluence: trend + vwap + RSI not extreme
  let score = 0;
  if (above || below) score += 2;
  if ((above && price > vwap) || (below && price < vwap)) score += 1;
  if (rsi >= 35 && rsi <= 65) score += 1;

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-3 space-y-2" data-testid="signal-panel">
      <h3 className="text-[0.6rem] font-black uppercase tracking-wider text-zinc-500 flex items-center gap-1.5">
        <Radio className="w-3.5 h-3.5 text-[#007AFF]" /> Signal Engine
      </h3>

      <div className="text-center py-2">
        <div className="text-[0.5rem] tracking-wider text-zinc-500 mb-0.5">CURRENT BIAS</div>
        <div className="text-xl font-black tracking-tight" style={{ color: biasColor }} data-testid="signal-bias">{bias}</div>
        <div className="text-[0.55rem] text-zinc-500 mt-0.5">Confluence: {score}/4</div>
      </div>

      <div className="border-t border-white/5 pt-2 space-y-1 text-[0.55rem] font-mono">
        <div className="flex justify-between">
          <span className="text-zinc-500">Price</span>
          <span className="text-white">{price.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500">EMA21</span>
          <span className={price > ema21 ? "text-[#34C759]" : "text-[#FF3B30]"}>{ema21.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500">VWAP</span>
          <span className={price > vwap ? "text-[#34C759]" : "text-[#FF3B30]"}>{vwap.toFixed(2)}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-zinc-500">RSI</span>
          <span className={rsi > 70 ? "text-[#FF3B30]" : rsi < 30 ? "text-[#34C759]" : "text-zinc-300"}>{rsi}</span>
        </div>
      </div>
    </div>
  );
}
