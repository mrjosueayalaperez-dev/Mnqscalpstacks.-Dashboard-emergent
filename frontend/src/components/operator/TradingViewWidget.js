import React, { useEffect, useRef, useState } from "react";
import { BarChart3, Wifi, WifiOff } from "lucide-react";

/**
 * TradingView Advanced Chart widget — real-time CME futures via the official
 * embed. Symbol `CME_MINI:MNQ1!` is the continuous front-month contract that
 * auto-rolls every quarter (currently MNQH26 → MNQM26 in March).
 *
 * No desync risk: this is the SAME data source you see on tradingview.com.
 */
export default function TradingViewWidget({ wsConnected, lastTick }) {
  const containerRef = useRef(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!containerRef.current) return undefined;
    const container = containerRef.current;
    container.replaceChildren(); // safe: clear our own owned DOM

    const div = document.createElement("div");
    div.className = "tradingview-widget-container__widget";
    div.style.height = "100%";
    div.style.width = "100%";
    container.appendChild(div);

    const script = document.createElement("script");
    script.type = "text/javascript";
    script.src = "https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js";
    script.async = true;
    // safe: hardcoded TradingView embed config — never user input. This is the
    // official embed pattern; the <script> tag expects its body to contain a
    // JSON config that TV's loader parses. textContent prevents accidental
    // HTML parsing.
    script.textContent = JSON.stringify({
      autosize: true,
      symbol: "CME_MINI:MNQ1!",
      interval: "1",
      timezone: "America/New_York",
      theme: "dark",
      style: "1",
      locale: "en",
      enable_publishing: false,
      withdateranges: true,
      hide_side_toolbar: false,
      allow_symbol_change: false,
      details: true,
      hotlist: false,
      calendar: false,
      studies: [
        "STD;EMA",
        "STD;EMA",
        "STD;VWAP",
        "STD;Volume",
        "STD;Sessions",
      ],
      studies_overrides: {
        "moving average exponential.length": 9,
        "moving average exponential.plot.color": "#FFCC00",
      },
      backgroundColor: "rgba(10, 10, 10, 1)",
      gridColor: "rgba(255, 255, 255, 0.04)",
      support_host: "https://www.tradingview.com",
    });
    script.onload = () => setReady(true);
    container.appendChild(script);

    return () => {
      try { container.replaceChildren(); } catch { /* ignore */ }
    };
  }, []);

  return (
    <div
      className="relative w-full h-full bg-[#0A0A0A] border border-white/10 rounded-sm overflow-hidden"
      data-testid="tv-widget"
    >
      {/* Header overlay */}
      <div className="absolute top-0 left-0 right-0 z-10 px-3 py-1.5 flex items-center justify-between border-b border-white/5 bg-[#0A0A0A]/85 backdrop-blur-sm pointer-events-none">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-3.5 h-3.5 text-[#34C759]" />
          <span className="text-[0.65rem] font-black tracking-wider text-white">CME_MINI:MNQ1!</span>
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
          <div className="flex items-center gap-1 px-1.5 py-0.5 rounded-sm bg-white/5" title={wsConnected ? "WebSocket live" : "WebSocket reconnecting"}>
            {wsConnected ? <Wifi className="w-3 h-3 text-[#34C759]" /> : <WifiOff className="w-3 h-3 text-[#FF3B30]" />}
            <span className={`text-[0.5rem] font-bold tracking-wider ${wsConnected ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
              {wsConnected ? "LIVE" : "RECONNECT"}
            </span>
          </div>
        </div>
      </div>

      <div ref={containerRef} className="absolute inset-0 pt-7" />

      {/* Watermark */}
      <div className="absolute bottom-1 right-12 z-10 pointer-events-none select-none opacity-30">
        <span className="text-[0.55rem] font-black tracking-widest text-white/40">MNQ • SCALP STACKS</span>
      </div>

      {!ready && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <span className="text-[0.65rem] text-zinc-500">Loading TradingView…</span>
        </div>
      )}
    </div>
  );
}
