import React from "react";
import { BarChart3, Wifi, WifiOff } from "lucide-react";
import { buildTvEmbedUrl, PROXY_LABEL } from "@/lib/tvEmbedUrl";

/**
 * TradingView chart — deterministic direct `widgetembed` iframe (see
 * lib/tvEmbedUrl.js for why we bypass the official embed script and chart
 * CAPITALCOM:US100 instead of the embed-blocked CME_MINI:MNQ1!). True MNQ
 * prices come from our own WebSocket feed (header overlay).
 */
export default function TradingViewWidget({ wsConnected, lastTick }) {
  return (
    <div
      className="relative w-full h-full bg-[#0A0A0A] border border-white/10 rounded-sm overflow-hidden"
      data-testid="tv-widget"
    >
      {/* Header overlay */}
      <div className="absolute top-0 left-0 right-0 z-10 px-3 py-1.5 flex items-center justify-between border-b border-white/5 bg-[#0A0A0A]/85 backdrop-blur-sm pointer-events-none">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-3.5 h-3.5 text-[#34C759]" />
          <span className="text-[0.65rem] font-black tracking-wider text-white">MNQ <span className="text-[#FFCC00] font-mono font-normal" data-testid="chart-symbol-label">· {PROXY_LABEL}</span></span>
          {lastTick?.price && (
            <span className="text-[0.65rem] font-mono text-zinc-300">
              {Number(lastTick.price).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          )}
          {typeof lastTick?.change === "number" && (
            <span className={`text-[0.55rem] font-mono ${lastTick.change >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
              {lastTick.change >= 0 ? "+" : ""}{lastTick.change} ({lastTick.change_percent}%)
            </span>
          )}
        </div>
        <div className="flex items-center gap-2 pointer-events-auto">
          <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-sm bg-white/5" title={wsConnected ? "WebSocket connected" : "WebSocket reconnecting"}>
            {wsConnected ? <Wifi className="w-3 h-3 text-[#34C759]" /> : <WifiOff className="w-3 h-3 text-[#FF3B30]" />}
            <span className={`text-[0.5rem] font-bold tracking-wider ${wsConnected ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
              {wsConnected ? "CONNECTED" : "RECONNECT"}
            </span>
          </div>
        </div>
      </div>

      <div className="absolute inset-0 pt-7">
        <iframe
          title="MNQ operator chart"
          src={buildTvEmbedUrl({ interval: "1", hideSideToolbar: false, withDateRanges: true })}
          className="w-full h-full border-0"
          allowFullScreen
        />
      </div>

      {/* Watermark */}
      <div className="absolute bottom-1 right-12 z-10 pointer-events-none select-none opacity-30">
        <span className="text-[0.55rem] font-black tracking-widest text-white/40">MNQ • SCALP STACKS</span>
      </div>
    </div>
  );
}
