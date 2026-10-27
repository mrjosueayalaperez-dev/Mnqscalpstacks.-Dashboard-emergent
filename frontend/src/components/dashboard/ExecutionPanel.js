import React, { useCallback, useEffect, useRef, useState } from "react";
import axios from "axios";
import { toast } from "sonner";
import { CheckSquare, Share2, Shield, Volume2, VolumeX, XCircle, Zap } from "lucide-react";
import useMnqLive from "@/components/operator/useMnqLive";
import { shareTradeCard } from "@/lib/shareCard";
import { playSignalSound } from "@/lib/signalSound";
import { ChartModeSwitcher } from "@/components/dashboard/ChartModeSwitcher";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const QTYS = [1, 2, 3, 5, 10];

const fmt = (v) =>
  typeof v === "number" ? v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—";

const gradeOf = (score) => (score >= 3 ? { g: "A+", cls: "border-[#34C759] text-[#34C759] bg-[#34C759]/10" }
  : score === 2 ? { g: "B", cls: "border-[#007AFF] text-[#007AFF] bg-[#007AFF]/10" }
  : { g: "C", cls: "border-zinc-500 text-zinc-400 bg-white/5" });

/** Graded live signal card — shows when an active setup exists. */
const SignalCard = ({ signal, onExecute, busy }) => {
  if (!signal) return null;
  const { g, cls } = gradeOf(signal.confluence_score ?? 0);
  const confidence = signal.confidence ?? Math.min(60 + (signal.confluence_score ?? 0) * 12, 95);
  const long = signal.side === "long";
  return (
    <div className={`border rounded-sm p-2.5 ${cls}`} data-testid="signal-card">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className={`px-1.5 py-0.5 text-[0.65rem] font-black rounded-sm border ${cls}`} data-testid="signal-grade">{g}</span>
          <span className={`text-xs font-black ${long ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
            {long ? "▲ LONG" : "▼ SHORT"} {signal.symbol}
          </span>
          <span className="text-[0.6rem] font-mono text-zinc-400" data-testid="signal-confidence">{confidence}% conf</span>
        </div>
        <button
          onClick={() => onExecute(long ? "BUY" : "SELL")}
          disabled={busy}
          className={`px-3 py-1 text-[0.6rem] font-black tracking-wider rounded-sm text-black transition-colors disabled:opacity-50 ${long ? "bg-[#34C759] hover:bg-[#2DB84E]" : "bg-[#FF3B30] hover:bg-[#E0352B] text-white"}`}
          data-testid="signal-execute-btn"
        >
          <Zap className="w-3 h-3 inline -mt-0.5" /> EXECUTE
        </button>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1.5 text-[0.6rem] font-mono text-zinc-400">
        <span>ENTRY <span className="text-white font-bold">{fmt(signal.entry_price)}</span></span>
        <span>STOP <span className="text-[#FF3B30] font-bold">{fmt(signal.stop_loss)}</span></span>
        <span>TP1 <span className="text-[#34C759] font-bold">{fmt(signal.tp1)}</span></span>
        <span>TP2 <span className="text-[#34C759] font-bold">{fmt(signal.tp2)}</span></span>
      </div>
    </div>
  );
};

/**
 * ExecutionPanel — mobile-first trading strip at the very top of the dashboard.
 * Big live price, one-thumb BUY/SELL, risk pill, qty selector, graded signal card.
 * Orders route through the same server-side engine as the operator cockpit.
 */
export default function ExecutionPanel({ checklistDone = 0, checklistTotal = 0, chartMode = "standard", onChartMode }) {
  const { tick, connected } = useMnqLive();
  const [qty, setQty] = useState(1);
  const [state, setState] = useState(null);
  const [signal, setSignal] = useState(null);
  const [busy, setBusy] = useState(false);
  const [soundOn, setSoundOn] = useState(() => localStorage.getItem("signal_sound") !== "off");
  const cooldownRef = useRef(0);
  const lastSignalIdRef = useRef(null);

  // Distinct chime when a NEW LIVE signal fires (paper tests stay silent)
  useEffect(() => {
    if (!signal?.id) return;
    const isTest = signal.is_test || signal.source === "test";
    if (lastSignalIdRef.current && lastSignalIdRef.current !== signal.id && !isTest) {
      if (soundOn) playSignalSound(signal.side);
      toast.info(`PAPER · New ${signal.side.toUpperCase()} signal @ ${fmt(signal.entry_price)}`);
      window.dispatchEvent(new CustomEvent("mnq:new-live-signal", { detail: { id: signal.id, side: signal.side } }));
    }
    lastSignalIdRef.current = signal.id;
  }, [signal?.id, signal?.side, signal?.entry_price, signal?.is_test, signal?.source, soundOn]);

  const toggleSound = () => {
    const next = !soundOn;
    setSoundOn(next);
    localStorage.setItem("signal_sound", next ? "on" : "off");
    if (next) playSignalSound("long");
  };

  const refresh = useCallback(async () => {
    try {
      const [s, sig] = await Promise.all([
        axios.get(`${API}/operator/state`),
        axios.get(`${API}/signals?limit=1&status=active`),
      ]);
      setState(s.data);
      const next = Array.isArray(sig.data) && sig.data.length ? sig.data[0] : null;
      // Arm the new-punch detector even when there's no active signal yet
      if (next === null && lastSignalIdRef.current === null) lastSignalIdRef.current = "none";
      setSignal(next);
    } catch (e) {
      console.warn("[Exec] refresh failed:", e?.message || e);
    }
  }, []);

  useEffect(() => {
    refresh();
    const t = setInterval(refresh, 5000);
    return () => clearInterval(t);
  }, [refresh]);

  const placeOrder = async (action) => {
    const isClose = action.startsWith("CLOSE");
    if (!isClose && Date.now() - cooldownRef.current < 1600) {
      toast.warning("Cooldown — wait a second between orders");
      return;
    }
    setBusy(true);
    try {
      const { data } = await axios.post(`${API}/operator/order`, {
        action, qty, order_type: "MARKET", preset: "SNIPE_2R", sl_ticks: 40, tp_ticks: 120,
      });
      cooldownRef.current = Date.now();
      toast.success(`SIM · ${action} ${qty} MNQ LOGGED @ ${fmt(data.order?.fill_price)}`, {
        description: "Simulated fill (bracket 40t/120t) — no broker routing",
      });
      refresh();
    } catch (e) {
      toast.error(`SIM · ${action} rejected`, { description: e.response?.data?.detail || e.message });
    }
    setBusy(false);
  };

  const closePosition = async () => {
    const side = state?.position?.side;
    if (!side) { toast.info("No open position"); return; }
    await placeOrder(side === "LONG" ? "CLOSE_LONG" : "CLOSE_SHORT");
  };

  const flatten = async () => {
    setBusy(true);
    try {
      await axios.post(`${API}/operator/control/flatten`);
      toast.success("SIM · FLATTENED — simulated positions closed");
      refresh();
    } catch (e) {
      toast.error("SIM · Flatten failed");
    }
    setBusy(false);
  };

  const up = (tick?.change ?? 0) >= 0;
  const pnl = state?.daily_pnl ?? 0;
  const risky = state?.kill_switch || pnl <= (state?.max_daily_loss ?? -100) * 0.8;
  const pos = state?.position;

  return (
    <div className="col-span-1 md:col-span-4 lg:col-span-12 bg-[#0D0D0F] border border-white/10 rounded-sm p-3 space-y-3" data-testid="execution-panel">
      {/* Price row */}
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[0.55rem] uppercase tracking-[0.2em] text-zinc-500">MNQ</span>
            <span className={`w-1.5 h-1.5 rounded-full ${connected ? "bg-[#34C759] animate-pulse" : "bg-[#FF3B30]"}`} />
          </div>
          <div className="flex items-baseline gap-2">
            <span className={`font-mono font-black text-3xl md:text-4xl ${up ? "text-[#34C759]" : "text-[#FF3B30]"}`} data-testid="exec-live-price">
              {fmt(tick?.price)}
            </span>
            <span className={`font-mono text-xs font-bold ${up ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
              {up ? "+" : ""}{fmt(tick?.change)} ({tick?.change_percent ?? 0}%)
            </span>
          </div>
          <div className="flex gap-3 text-[0.6rem] font-mono text-zinc-500 mt-0.5">
            <span>H <span className="text-[#34C759]">{fmt(tick?.day_high)}</span></span>
            <span>L <span className="text-[#FF3B30]">{fmt(tick?.day_low)}</span></span>
          </div>
        </div>

        {/* Risk pill + chart-mode switch + checklist chip */}
        <div className="flex flex-col items-end gap-1.5">
          <div className="flex items-center gap-2">
            <span
              className={`flex items-center gap-1.5 px-2 py-1 rounded-full text-[0.6rem] font-black tracking-wider border ${
                risky ? "border-[#FF3B30]/50 text-[#FF3B30] bg-[#FF3B30]/10" : "border-[#34C759]/40 text-[#34C759] bg-[#34C759]/10"
              }`}
              data-testid="risk-pill"
            >
              <Shield className="w-3 h-3" />
              {state?.kill_switch ? "LOCKED" : risky ? "AT RISK" : "SAFE"} · ${Math.abs(state?.max_daily_loss ?? 100).toLocaleString()} limit · {state?.daily_trades ?? 0}/{state?.max_daily_trades ?? 20}
            </span>
            {onChartMode && <ChartModeSwitcher mode={chartMode} onChange={onChartMode} />}
            <button
              onClick={toggleSound}
              aria-label="Toggle signal sound"
              className={`w-8 h-8 shrink-0 rounded-full flex items-center justify-center border transition-colors ${soundOn ? "border-[#FFCC00]/50 bg-[#FFCC00]/10 text-[#FFCC00]" : "border-white/15 bg-white/5 text-zinc-500"}`}
              data-testid="signal-sound-toggle"
            >
              {soundOn ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
            </button>
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={async () => {
                const result = await shareTradeCard({
                  side: "SESSION",
                  qty: state?.daily_trades ?? 0,
                  pnl: state?.daily_pnl ?? 0,
                  grade: `${state?.daily_trades ?? 0} TRADES`,
                });
                toast.success(result === "shared" ? "Session card shared!" : "Session card downloaded — post it!");
              }}
              className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.55rem] font-bold border border-[#007AFF]/40 text-[#007AFF] hover:bg-[#007AFF]/10 transition-colors"
              data-testid="share-session-btn"
            >
              <Share2 className="w-3 h-3" /> SHARE
            </button>
            {pos?.side && (
              <span className={`px-2 py-0.5 rounded-full text-[0.55rem] font-black border ${pos.side === "LONG" ? "border-[#34C759]/40 text-[#34C759]" : "border-[#FF3B30]/40 text-[#FF3B30]"}`} data-testid="exec-position">
                {pos.side} {pos.qty} @ {fmt(pos.avg_entry)}
              </span>
            )}
            {checklistTotal > 0 && (
              <button
                onClick={() => document.querySelector('[data-testid="checklist-panel"]')?.scrollIntoView({ behavior: "smooth" })}
                className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[0.55rem] font-bold border border-white/15 text-zinc-400 hover:text-white transition-colors"
                data-testid="checklist-chip"
              >
                <CheckSquare className="w-3 h-3" /> {checklistDone}/{checklistTotal}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Execution bar — BUY/SELL always share one row (one-thumb) */}
      <div className="space-y-2">
        <div className="flex gap-1 justify-between sm:justify-start" data-testid="qty-selector">
          {QTYS.map((q) => (
            <button
              key={q}
              onClick={() => setQty(q)}
              className={`flex-1 sm:flex-none sm:w-10 py-2 rounded-sm text-xs font-black font-mono transition-colors ${
                qty === q ? "bg-[#007AFF] text-white" : "bg-white/5 text-zinc-400 hover:bg-white/10"
              }`}
              data-testid={`qty-${q}`}
            >
              {q}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => placeOrder("BUY")}
            disabled={busy}
            className="py-3 bg-[#34C759] hover:bg-[#2DB84E] text-black text-sm font-black tracking-wider rounded-sm transition-colors disabled:opacity-50"
            data-testid="exec-buy-btn"
          >
            BUY MARKET
          </button>
          <button
            onClick={() => placeOrder("SELL")}
            disabled={busy}
            className="py-3 bg-[#FF3B30] hover:bg-[#E0352B] text-white text-sm font-black tracking-wider rounded-sm transition-colors disabled:opacity-50"
            data-testid="exec-sell-btn"
          >
            SELL MARKET
          </button>
        </div>
        <div className="flex gap-2">
          <button
            onClick={closePosition}
            disabled={busy}
            className="flex-1 py-2 bg-white/5 hover:bg-white/10 border border-white/15 text-zinc-300 text-xs font-black rounded-sm transition-colors disabled:opacity-50"
            data-testid="exec-close-btn"
          >
            CLOSE
          </button>
          <button
            onClick={flatten}
            disabled={busy}
            className="flex-1 flex items-center justify-center gap-1 py-2 bg-[#FF3B30]/15 hover:bg-[#FF3B30]/25 border border-[#FF3B30]/40 text-[#FF3B30] text-xs font-black rounded-sm transition-colors disabled:opacity-50"
            data-testid="exec-flatten-btn"
          >
            <XCircle className="w-3.5 h-3.5" /> FLATTEN
          </button>
        </div>
      </div>

      {/* OPEN POSITION — live execution data for what you're holding */}
      {pos?.side && (() => {
        const dir = pos.side === "LONG" ? 1 : -1;
        const live = tick?.price;
        const pts = typeof live === "number" && pos.avg_entry ? (live - pos.avg_entry) * dir : null;
        const usd = pts !== null ? pts * 2 * (pos.qty || 1) : null;
        const winning = (usd ?? 0) >= 0;
        return (
          <div
            className={`border rounded-sm p-2.5 ${pos.side === "LONG" ? "border-[#34C759]/40 bg-[#34C759]/5" : "border-[#FF3B30]/40 bg-[#FF3B30]/5"}`}
            data-testid="open-position-card"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className={`text-xs font-black ${pos.side === "LONG" ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                {pos.side === "LONG" ? "▲" : "▼"} OPEN {pos.side} · {pos.qty} MNQ
              </span>
              <span className={`font-mono text-sm font-black ${winning ? "text-[#34C759]" : "text-[#FF3B30]"}`} data-testid="open-position-pnl">
                {usd !== null ? `${winning ? "+" : "-"}$${Math.abs(usd).toFixed(2)}` : "—"}
                <span className="text-[0.6rem] text-zinc-400 font-bold ml-1">
                  ({pts !== null ? `${pts >= 0 ? "+" : ""}${pts.toFixed(2)} pts` : "—"})
                </span>
              </span>
            </div>
            <div className="flex flex-wrap items-center justify-between gap-2 mt-1.5">
              <div className="flex flex-wrap gap-x-3 gap-y-0.5 text-[0.6rem] font-mono text-zinc-400">
                <span>AVG ENTRY <span className="text-white font-bold">{fmt(pos.avg_entry)}</span></span>
                <span>MARK <span className="text-white font-bold">{fmt(live)}</span></span>
                <span>VALUE/PT <span className="text-white font-bold">${(2 * (pos.qty || 1)).toFixed(0)}</span></span>
              </div>
              <button
                onClick={closePosition}
                disabled={busy}
                className="px-3 py-1 text-[0.6rem] font-black tracking-wider rounded-sm bg-white/10 hover:bg-white/20 text-white transition-colors disabled:opacity-50"
                data-testid="open-position-close-btn"
              >
                CLOSE POSITION
              </button>
            </div>
          </div>
        );
      })()}

      <SignalCard signal={signal} onExecute={placeOrder} busy={busy} />
    </div>
  );
}
