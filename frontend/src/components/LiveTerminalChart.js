import React, { useEffect, useRef, useState } from "react";
import { Activity, Wifi, WifiOff, TrendingUp, TrendingDown, Minus } from "lucide-react";
import useMnqLive from "@/components/operator/useMnqLive";
import { buildTvEmbedUrl } from "@/lib/tvEmbedUrl";
import SignalChart from "@/components/dashboard/SignalChart";

const INTERVALS = [
  { label: "SIGNAL", tv: "signal" },
  { label: "5m+1m", tv: "stack" },
  { label: "1m", tv: "1" },
  { label: "5m", tv: "5" },
  { label: "15m", tv: "15" },
  { label: "1h", tv: "60" },
  { label: "4h", tv: "240" },
  { label: "D", tv: "D" },
];

const fmt = (v) =>
  typeof v === "number"
    ? v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "—";

/**
 * Deterministic TradingView chart — direct `widgetembed` iframe (see
 * lib/tvEmbedUrl.js for why we bypass the official embed script). The live
 * tape above the chart shows the TRUE MNQ price from our own WebSocket feed;
 * the chart plots CAPITALCOM:US100, a 1:1 MNQ structure proxy.
 */
const TvEmbed = ({ interval }) => (
  <iframe
    key={interval}
    title="MNQ terminal chart"
    src={buildTvEmbedUrl({ interval, hideSideToolbar: true, withDateRanges: false })}
    className="absolute inset-0 w-full h-full border-0"
    allowFullScreen
  />
);

/** Big live price with green/red flash on tick direction. */
const LivePrice = ({ tick }) => {
  const prevRef = useRef(null);
  const [dir, setDir] = useState(0);

  useEffect(() => {
    if (typeof tick?.price !== "number") return undefined;
    if (prevRef.current !== null && tick.price !== prevRef.current) {
      setDir(tick.price > prevRef.current ? 1 : -1);
      const t = setTimeout(() => setDir(0), 600);
      prevRef.current = tick.price;
      return () => clearTimeout(t);
    }
    prevRef.current = tick.price;
    return undefined;
  }, [tick?.price]);

  const up = (tick?.change ?? 0) >= 0;
  return (
    <div className="flex items-baseline gap-2 md:gap-3" data-testid="terminal-live-price">
      <span
        className={`font-mono font-black text-2xl md:text-4xl transition-colors duration-300 ${
          dir === 1 ? "text-[#34C759]" : dir === -1 ? "text-[#FF3B30]" : "text-white"
        }`}
        style={dir !== 0 ? { textShadow: `0 0 18px ${dir === 1 ? "rgba(52,199,89,0.6)" : "rgba(255,59,48,0.6)"}` } : undefined}
      >
        {fmt(tick?.price)}
      </span>
      <span className={`font-mono text-xs md:text-sm font-bold ${up ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
        {up ? "▲" : "▼"} {up ? "+" : ""}{fmt(tick?.change)} ({tick?.change_percent ?? 0}%)
      </span>
    </div>
  );
};

const StatCell = ({ label, value, color = "text-white", testId }) => (
  <div className="flex flex-col items-start px-3 py-1.5 border-r border-white/5 last:border-r-0 min-w-0" data-testid={testId}>
    <span className="text-[0.55rem] uppercase tracking-[0.15em] text-zinc-500 whitespace-nowrap">{label}</span>
    <span className={`font-mono text-xs md:text-sm font-bold ${color} whitespace-nowrap`}>{value}</span>
  </div>
);

/** Live confluence signal computed from EMA21 + VWAP + RSI. */
const SignalBar = ({ tick }) => {
  if (!tick?.price) return null;
  const aboveEma = tick.price > tick.ema21;
  const aboveVwap = tick.price > tick.vwap;
  const rsi = tick.rsi ?? 50;
  const isBuy = aboveEma && aboveVwap && rsi < 72;
  const isSell = !aboveEma && !aboveVwap && rsi > 28;

  const chips = [
    { label: `EMA21 ${aboveEma ? "ABOVE" : "BELOW"}`, ok: aboveEma },
    { label: `VWAP ${aboveVwap ? "ABOVE" : "BELOW"}`, ok: aboveVwap },
    { label: `RSI ${rsi}`, ok: rsi >= 45 && rsi <= 72 },
  ];

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 border-t border-white/10 bg-white/[0.02]" data-testid="terminal-signal-bar">
      <div className="flex items-center gap-2">
        <span className="text-[0.55rem] uppercase tracking-[0.2em] text-zinc-500">Live Signal</span>
        {isBuy ? (
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-[#34C759]/15 border border-[#34C759]/40 text-[#34C759] text-xs font-black tracking-wider" data-testid="terminal-signal-buy">
            <TrendingUp className="w-3.5 h-3.5" /> BUY PUNCH
          </span>
        ) : isSell ? (
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-[#FF3B30]/15 border border-[#FF3B30]/40 text-[#FF3B30] text-xs font-black tracking-wider" data-testid="terminal-signal-sell">
            <TrendingDown className="w-3.5 h-3.5" /> SELL PUNCH
          </span>
        ) : (
          <span className="flex items-center gap-1.5 px-2 py-0.5 rounded-sm bg-white/5 border border-white/15 text-zinc-400 text-xs font-black tracking-wider" data-testid="terminal-signal-neutral">
            <Minus className="w-3.5 h-3.5" /> NEUTRAL — WAIT
          </span>
        )}
      </div>
      <div className="flex items-center gap-1.5">
        {chips.map((c) => (
          <span
            key={c.label}
            className={`px-1.5 py-0.5 rounded-sm text-[0.55rem] font-mono font-bold tracking-wider border ${
              c.ok ? "border-[#34C759]/30 text-[#34C759] bg-[#34C759]/10" : "border-[#FF3B30]/30 text-[#FF3B30] bg-[#FF3B30]/10"
            }`}
          >
            {c.label}
          </span>
        ))}
      </div>
    </div>
  );
};

/**
 * LiveTerminalChart — full-width dashboard terminal: official TradingView
 * Advanced Chart (CAPITALCOM:US100 — MNQ 1:1 proxy) framed by a live WebSocket tape
 * (price / session levels / indicators) and a real-time confluence signal bar.
 */
export default function LiveTerminalChart() {
  const { tick, connected } = useMnqLive();
  const [interval, setInterval_] = useState(() => localStorage.getItem("terminal_tf") || "stack");
  const pickInterval = (tv) => {
    setInterval_(tv);
    localStorage.setItem("terminal_tf", tv);
  };

  // Auto-flip to SIGNAL view the moment a new LIVE punch fires (event from ExecutionPanel)
  useEffect(() => {
    const flip = () => {
      setInterval_("signal");
      localStorage.setItem("terminal_tf", "signal");
    };
    window.addEventListener("mnq:new-live-signal", flip);
    return () => window.removeEventListener("mnq:new-live-signal", flip);
  }, []);

  return (
    <div className="col-span-1 md:col-span-4 lg:col-span-12 bg-[#0D0D0F] border border-white/10 rounded-sm overflow-hidden" data-testid="live-terminal-chart">
      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 border-b border-white/10 bg-[#0A0A0A]">
        <div className="flex items-center gap-2.5">
          <Activity className="w-4 h-4 text-[#34C759]" />
          <span className="text-xs md:text-sm font-black tracking-[0.2em] text-white">MNQ LIVE TERMINAL</span>
          <span className="hidden sm:inline text-[0.6rem] font-mono text-zinc-500">US100 CFD · TRACKS MNQ 1:1 · <span className="text-[#FFCC00]">TAPE ~10 MIN DELAYED</span></span>
          <div
            className={`flex items-center gap-1 px-1.5 py-0.5 rounded-sm ${connected ? "bg-[#34C759]/10" : "bg-[#FF3B30]/10"}`}
            data-testid="terminal-ws-status"
          >
            {connected ? <Wifi className="w-3 h-3 text-[#34C759]" /> : <WifiOff className="w-3 h-3 text-[#FF3B30]" />}
            <span className={`text-[0.5rem] font-bold tracking-wider ${connected ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
              {connected ? "LIVE" : "RECONNECT"}
            </span>
            {connected && <span className="w-1.5 h-1.5 rounded-full bg-[#34C759] animate-pulse" />}
          </div>
          {tick?.market_state && (
            <span className="hidden md:inline text-[0.55rem] font-mono uppercase tracking-wider text-zinc-500">
              {tick.market_state}
            </span>
          )}
        </div>

        {/* Timeframe selector */}
        <div className="flex items-center gap-1" data-testid="terminal-timeframes">
          {INTERVALS.map((iv) => (
            <button
              key={iv.tv}
              onClick={() => pickInterval(iv.tv)}
              data-testid={`terminal-tf-${iv.label}`}
              className={`px-2 py-1 rounded-sm text-[0.6rem] font-mono font-bold tracking-wider transition-colors duration-150 ${
                interval === iv.tv
                  ? "bg-[#007AFF] text-white"
                  : "bg-white/5 text-zinc-400 hover:bg-white/10 hover:text-white"
              }`}
            >
              {iv.label}
            </button>
          ))}
        </div>
      </div>

      {/* Live tape: price + session levels + indicators */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-2 px-3 py-2 border-b border-white/10">
        <LivePrice tick={tick} />
        <div className="flex flex-1 flex-wrap items-center justify-end overflow-x-auto">
          <StatCell label="Session High" value={fmt(tick?.day_high)} color="text-[#34C759]" testId="terminal-session-high" />
          <StatCell label="Session Low" value={fmt(tick?.day_low)} color="text-[#FF3B30]" testId="terminal-session-low" />
          <StatCell label="VWAP" value={fmt(tick?.vwap)} color="text-[#007AFF]" testId="terminal-vwap" />
          <StatCell label="EMA 9" value={fmt(tick?.ema9)} color="text-[#FFCC00]" testId="terminal-ema9" />
          <StatCell label="EMA 21" value={fmt(tick?.ema21)} testId="terminal-ema21" />
          <StatCell
            label="RSI 14"
            value={tick?.rsi ?? "—"}
            color={tick?.rsi > 70 ? "text-[#FF3B30]" : tick?.rsi < 30 ? "text-[#34C759]" : "text-white"}
            testId="terminal-rsi"
          />
        </div>
      </div>

      {/* Chart — SIGNAL (native candles + signal level lines), stacked 5m/1m TV, or single TV timeframe */}
      {interval === "signal" ? (
        <div data-testid="terminal-signal-stack">
          {[{ tf: "5m", label: "5m · BIAS" }, { tf: "1m", label: "1m · ENTRY" }].map((p) => (
            <div key={p.tf} className="relative w-full h-[340px] md:h-[430px] bg-[#0A0A0A] border-b border-white/10 last:border-b-0">
              <SignalChart interval={p.tf} />
              <div className="absolute bottom-8 left-2 z-10 pointer-events-none select-none px-1.5 py-0.5 rounded-sm bg-black/70 border border-white/10">
                <span className="text-[0.55rem] font-black tracking-widest text-[#007AFF]">MNQ · {p.label}</span>
              </div>
            </div>
          ))}
        </div>
      ) : interval === "stack" ? (
        <div data-testid="terminal-chart-stack">
          {[{ tv: "5", label: "5m · BIAS" }, { tv: "1", label: "1m · ENTRY" }].map((p) => (
            <div key={p.tv} className="relative w-full h-[340px] md:h-[430px] bg-[#0A0A0A] border-b border-white/10 last:border-b-0">
              <TvEmbed interval={p.tv} />
              <div className="absolute bottom-8 left-14 z-10 pointer-events-none select-none px-1.5 py-0.5 rounded-sm bg-black/70 border border-white/10">
                <span className="text-[0.55rem] font-black tracking-widest text-[#007AFF]">MNQ · {p.label}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="relative w-full h-[420px] md:h-[560px] bg-[#0A0A0A]">
          <TvEmbed interval={interval} />
          <div className="absolute bottom-2 right-14 z-10 pointer-events-none select-none opacity-30">
            <span className="text-[0.55rem] font-black tracking-widest text-white/40">MNQ • SCALP STACKS</span>
          </div>
        </div>
      )}

      <SignalBar tick={tick} />
    </div>
  );
}
