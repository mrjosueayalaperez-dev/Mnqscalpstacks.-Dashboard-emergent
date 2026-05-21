import React, { useState } from "react";
import {
  Zap, Shield, BarChart3, Activity, Cpu, Globe,
  Bell, Layers, Brain, CreditCard, Smartphone, Check, ExternalLink, Link2,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
// Build a tracked outbound URL: /api/r/{partner}?src={cta-id}
const track = (partner, src) =>
  `${BACKEND_URL}/api/r/${partner}?src=${encodeURIComponent(src)}`;

// ============ NINJATRADER SECTION ============
const NinjaTraderPanel = () => (
  <div className="col-span-1 md:col-span-4 lg:col-span-12 space-y-3" data-testid="ninjatrader-panel">
    <div className="flex items-center justify-between">
      <div>
        <h2 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2">
          <Cpu className="w-4 h-4 text-[#007AFF]" /> NinjaTrader Automation Center
        </h2>
        <p className="text-[0.65rem] text-zinc-500 mt-0.5">Deploy high-speed MNQ futures workflows with optimized execution models.</p>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {[
        { icon: Zap, title: "Semi-Auto Execution Engine", desc: "Execute confirmed scalp setups instantly with reduced hesitation.", cta: "Activate System", color: "#34C759", src: "ninja-activate-system" },
        { icon: Shield, title: "Advanced Risk Control", desc: "Dynamic stop-loss and position sizing protection for volatile MNQ sessions.", cta: "Configure Risk", color: "#FFCC00", src: "ninja-configure-risk" },
        { icon: Link2, title: "Fast Broker Connection", desc: "Connect NinjaTrader accounts and route trades efficiently.", cta: "Connect Broker", color: "#007AFF", src: "ninja-connect-broker" },
      ].map((card) => (
        <div key={card.title} className="p-4 bg-[#121212] border border-white/10 rounded-sm hover:border-white/20 transition-all group">
          <card.icon className="w-5 h-5 mb-3" style={{ color: card.color }} />
          <h3 className="text-sm font-bold text-white mb-1">{card.title}</h3>
          <p className="text-[0.65rem] text-zinc-500 leading-relaxed mb-3">{card.desc}</p>
          <a
            href={track("ninjatrader", card.src)}
            target="_blank"
            rel="noopener noreferrer sponsored"
            className="inline-flex items-center gap-1 text-[0.65rem] font-bold uppercase tracking-wider px-3 py-1.5 rounded-sm transition-all hover:opacity-80"
            style={{ backgroundColor: `${card.color}15`, color: card.color, border: `1px solid ${card.color}30` }}
            data-testid={`ninja-${card.src}`}
          >
            {card.cta} <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      ))}
    </div>

    <div className="p-4 bg-gradient-to-r from-[#007AFF]/10 via-[#121212] to-[#007AFF]/5 border border-[#007AFF]/20 rounded-sm flex flex-col md:flex-row items-center justify-between gap-4">
      <div>
        <h3 className="text-sm font-black text-white mb-1">Trade Faster with NinjaTrader + MNQ Scalp Stacks</h3>
        <p className="text-[0.6rem] text-zinc-400">Professional futures execution tools built for precision entries, controlled risk, and fast-moving market conditions.</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <a
          href={track("ninjatrader", "ninja-launch-setup")}
          target="_blank"
          rel="noopener noreferrer sponsored"
          className="px-3 py-1.5 bg-[#007AFF] text-white text-[0.65rem] font-bold rounded-sm hover:bg-[#3395FF] transition-colors inline-flex items-center gap-1"
          data-testid="ninja-launch-setup"
        >
          Launch Ninja Setup <ExternalLink className="w-3 h-3" />
        </a>
        <a href="/performance" className="px-3 py-1.5 bg-[#FFCC00]/15 text-[#FFCC00] text-[0.65rem] font-bold rounded-sm border border-[#FFCC00]/30 hover:bg-[#FFCC00]/25 transition-colors">
          Upgrade Pro
        </a>
      </div>
    </div>
  </div>
);

// ============ TRADINGVIEW SECTION ============
const TradingViewPanel = () => (
  <div className="col-span-1 md:col-span-4 lg:col-span-12 space-y-3" data-testid="tradingview-panel">
    <div className="flex items-center justify-between">
      <div>
        <h2 className="text-sm font-black text-white uppercase tracking-wider flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-[#34C759]" /> TradingView Signal Intelligence
        </h2>
        <p className="text-[0.65rem] text-zinc-500 mt-0.5">Advanced charting systems, alerts, and smart automation for MNQ scalpers.</p>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {[
        { icon: Bell, title: "Precision Entry Alerts", desc: "Receive high-quality signal confirmations directly from TradingView.", cta: "Enable Alerts", color: "#34C759", src: "tv-enable-alerts" },
        { icon: Layers, title: "MNQ Strategy Templates", desc: "Import ready-to-use layouts optimized for momentum scalping.", cta: "Load Templates", color: "#FFCC00", src: "tv-load-templates" },
        { icon: Brain, title: "AI Bias Detection", desc: "Market direction analysis using trend, volume, and momentum alignment.", cta: "View AI Signals", color: "#007AFF", src: "tv-ai-signals" },
      ].map((card) => (
        <div key={card.title} className="p-4 bg-[#121212] border border-white/10 rounded-sm hover:border-white/20 transition-all">
          <card.icon className="w-5 h-5 mb-3" style={{ color: card.color }} />
          <h3 className="text-sm font-bold text-white mb-1">{card.title}</h3>
          <p className="text-[0.65rem] text-zinc-500 leading-relaxed mb-3">{card.desc}</p>
          <a
            href={track("tradingview", card.src)}
            target="_blank"
            rel="noopener noreferrer sponsored"
            className="inline-flex items-center gap-1 text-[0.65rem] font-bold uppercase tracking-wider px-3 py-1.5 rounded-sm transition-all hover:opacity-80"
            style={{ backgroundColor: `${card.color}15`, color: card.color, border: `1px solid ${card.color}30` }}
            data-testid={`tv-${card.src}`}
          >
            {card.cta} <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      ))}
    </div>

    <div className="p-4 bg-gradient-to-r from-[#34C759]/10 via-[#121212] to-[#34C759]/5 border border-[#34C759]/20 rounded-sm flex flex-col md:flex-row items-center justify-between gap-4">
      <div>
        <h3 className="text-sm font-black text-white mb-1">Upgrade Your TradingView Workflow</h3>
        <p className="text-[0.6rem] text-zinc-400">Built for traders who need fast signal confirmation, clean execution, and scalable futures strategies.</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <a
          href={track("tradingview", "tv-connect")}
          target="_blank"
          rel="noopener noreferrer sponsored"
          className="px-3 py-1.5 bg-[#34C759] text-black text-[0.65rem] font-bold rounded-sm hover:bg-[#2DB84E] transition-colors inline-flex items-center gap-1"
          data-testid="tv-connect"
        >
          Connect TradingView <ExternalLink className="w-3 h-3" />
        </a>
        <a href="/performance" className="px-3 py-1.5 bg-[#FFCC00]/15 text-[#FFCC00] text-[0.65rem] font-bold rounded-sm border border-[#FFCC00]/30 hover:bg-[#FFCC00]/25 transition-colors">
          Start Pro Trial
        </a>
      </div>
    </div>
  </div>
);

// ============ GPAY FLOATING WIDGET ============
const GPayWidget = () => {
  const [open, setOpen] = useState(false);

  return (
    <div className="fixed bottom-4 right-4 z-50" data-testid="gpay-widget">
      {open && (
        <div className="mb-3 w-64 bg-[#121212] border border-[#FFCC00]/30 rounded-sm shadow-2xl p-4 animate-fade-in-up">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-xs font-black text-white flex items-center gap-1.5">
              <Smartphone className="w-3.5 h-3.5 text-[#FFCC00]" /> Fast Checkout with GPay
            </h4>
            <button onClick={() => setOpen(false)} className="text-zinc-500 hover:text-white text-xs" data-testid="gpay-close">X</button>
          </div>
          <ul className="space-y-1.5 mb-3">
            {["One-click upgrades", "Secure payment", "Instant activation", "Mobile optimized"].map((f) => (
              <li key={f} className="flex items-center gap-2 text-[0.6rem] text-zinc-400">
                <Check className="w-3 h-3 text-[#34C759]" />{f}
              </li>
            ))}
          </ul>
          <a
            href={track("gpay", "gpay-checkout")}
            target="_blank"
            rel="noopener noreferrer sponsored"
            className="w-full flex items-center justify-center gap-2 py-2 bg-[#FFCC00] text-black text-xs font-black rounded-sm hover:bg-[#FFCC00]/80 transition-colors"
            data-testid="gpay-checkout"
          >
            <CreditCard className="w-4 h-4" /> Pay with GPay
          </a>
        </div>
      )}
      <button
        onClick={() => setOpen(!open)}
        className="w-12 h-12 bg-[#FFCC00] text-black rounded-full shadow-lg flex items-center justify-center hover:scale-110 transition-transform hover:shadow-[0_0_20px_rgba(255,204,0,0.3)]"
        data-testid="gpay-fab"
      >
        <CreditCard className="w-5 h-5" />
      </button>
    </div>
  );
};

// ============ MARKET SIDEBAR WIDGETS ============
const MarketSidebar = ({ mnqData }) => {
  const price = mnqData?.close || mnqData?.price || 0;
  const ema21 = mnqData?.ema21 || 0;
  const vwap = mnqData?.vwap || 0;
  const rsi = mnqData?.rsi || 50;

  const trendBias = price > ema21 && price > vwap ? "BULLISH" : price < ema21 && price < vwap ? "BEARISH" : "NEUTRAL";
  const volatility = rsi > 70 || rsi < 30 ? "HIGH" : rsi > 60 || rsi < 40 ? "MODERATE" : "LOW";

  const hour = new Date().getUTCHours();
  const nyHour = (hour - 5 + 24) % 24;
  const nySession = nyHour >= 9 && nyHour < 16 ? "OPEN" : "CLOSED";

  return (
    <div className="col-span-1 md:col-span-2 lg:col-span-3 space-y-3" data-testid="market-sidebar">
      <div className="bg-[#121212] border border-white/10 rounded-sm p-3">
        <h4 className="text-[0.55rem] font-bold uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1">
          <Globe className="w-3 h-3" /> Market Conditions
        </h4>
        <div className="space-y-2">
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">NY Session</span>
            <span className={`font-bold ${nySession === "OPEN" ? "text-[#34C759]" : "text-zinc-600"}`}>{nySession}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">Volatility</span>
            <span className={`font-bold ${volatility === "HIGH" ? "text-[#FF3B30]" : volatility === "MODERATE" ? "text-[#FFCC00]" : "text-[#34C759]"}`}>{volatility}</span>
          </div>
          <div className="flex justify-between text-xs">
            <span className="text-zinc-500">Trend Bias</span>
            <span className={`font-bold ${trendBias === "BULLISH" ? "text-[#34C759]" : trendBias === "BEARISH" ? "text-[#FF3B30]" : "text-[#FFCC00]"}`}>{trendBias}</span>
          </div>
        </div>
      </div>

      <div className="bg-[#121212] border border-white/10 rounded-sm p-3">
        <h4 className="text-[0.55rem] font-bold uppercase tracking-wider text-zinc-500 mb-2 flex items-center gap-1">
          <Activity className="w-3 h-3" /> Futures Sentiment
        </h4>
        <div className="space-y-1.5">
          {[
            { text: "MNQ holding above session VWAP", sentiment: "bullish" },
            { text: "Fed rate decision pending", sentiment: "neutral" },
            { text: "Nasdaq tech earnings in focus", sentiment: "bullish" },
          ].map((item, i) => (
            <div key={`news-${i}`} className="flex items-start gap-2 text-[0.6rem]">
              <div className={`w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${
                item.sentiment === "bullish" ? "bg-[#34C759]" : item.sentiment === "bearish" ? "bg-[#FF3B30]" : "bg-[#FFCC00]"
              }`} />
              <span className="text-zinc-400">{item.text}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export { NinjaTraderPanel, TradingViewPanel, GPayWidget, MarketSidebar };
