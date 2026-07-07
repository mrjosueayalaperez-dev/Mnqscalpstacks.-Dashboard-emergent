import React, { useEffect, useRef, useState, useCallback } from "react";
import axios from "axios";
import { toast } from "sonner";
import { Bell, BellRing } from "lucide-react";
import { sounds } from "./useAudio";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LS_ALERTS = "operator.priceAlerts";

const Pill = ({ id, label, price, ticks, color, alerted, flashing, onToggle, testId }) => {
  const arrow = ticks > 0 ? "▲" : ticks < 0 ? "▼" : "—";
  return (
    <button
      type="button"
      onClick={() => onToggle(id, label, price)}
      data-testid={testId}
      title={`${label} @ ${price?.toFixed(2)} • ${alerted ? "Click to DISARM alert" : "Click to ARM alert"}`}
      className={`flex items-center gap-1.5 px-2 py-0.5 rounded-sm border bg-[#0F0F0F] transition-all cursor-pointer hover:brightness-125 ${
        alerted ? "ring-1 ring-[#FFCC00]/60 shadow-[0_0_8px_rgba(255,204,0,0.3)]" : ""
      } ${flashing ? "animate-pulse bg-[#FFCC00]/15" : ""}`}
      style={{ borderColor: alerted ? "#FFCC00" : `${color}55` }}
    >
      <span className="text-[0.55rem] font-black tracking-wider" style={{ color }}>{label}</span>
      <span className="text-[0.55rem] font-mono text-zinc-200">{price?.toFixed(2) ?? "—"}</span>
      {typeof ticks === "number" && (
        <span className="text-[0.5rem] font-mono opacity-70" style={{ color }}>
          {arrow}{Math.abs(ticks)}t
        </span>
      )}
      {alerted ? (
        <BellRing className="w-2.5 h-2.5 text-[#FFCC00]" />
      ) : (
        <Bell className="w-2.5 h-2.5 text-zinc-600 opacity-50" />
      )}
    </button>
  );
};

/**
 * KeyLevels — strip of PDH/PDL/PDC/Today's HLO with click-to-arm price alerts.
 *
 * Each pill is a toggle: click to arm a level. The hook watches `currentPrice`
 * deltas and fires a chime + toast + flash when price crosses the armed level
 * (from either direction). Armed alerts persist in localStorage.
 */
export default function KeyLevels({ currentPrice }) {
  const [ctx, setCtx] = useState(null);
  const [alerts, setAlerts] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem(LS_ALERTS) || "{}");
    } catch { return {}; }
  });
  const [flashing, setFlashing] = useState({}); // {pillId: true}
  const prevPriceRef = useRef(null);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/market/context`);
        if (active) setCtx(data);
      } catch (e) {
        console.warn("[KeyLevels] context fetch failed:", e?.message || e);
      }
    };
    load();
    const id = setInterval(load, 60000);
    return () => { active = false; clearInterval(id); };
  }, []);

  // Cross-detection on every price update
  useEffect(() => {
    if (!currentPrice) return;
    const prev = prevPriceRef.current;
    prevPriceRef.current = currentPrice;
    if (prev === null || prev === currentPrice) return;

    Object.entries(alerts).forEach(([id, alert]) => {
      const lvl = alert.price;
      if (!lvl) return;
      const crossedUp   = prev < lvl && currentPrice >= lvl;
      const crossedDown = prev > lvl && currentPrice <= lvl;
      if (crossedUp || crossedDown) {
        // Fire
        try {
          sounds.breakEven();
        } catch (e) {
          console.warn("[KeyLevels] audio playback blocked:", e?.message || e);
        }
        toast(`◆ ${alert.label} ${crossedUp ? "broken UP" : "broken DOWN"}`, {
          description: `${lvl.toFixed(2)} @ ${currentPrice.toFixed(2)}`,
          duration: 6000,
        });
        // Flash
        setFlashing((f) => ({ ...f, [id]: true }));
        setTimeout(() => setFlashing((f) => { const n = { ...f }; delete n[id]; return n; }), 2500);
        // Auto-disarm so it doesn't fire twice
        setAlerts((curr) => {
          const next = { ...curr };
          delete next[id];
          localStorage.setItem(LS_ALERTS, JSON.stringify(next));
          return next;
        });
      }
    });
  }, [currentPrice, alerts]);

  const toggleAlert = useCallback((id, label, price) => {
    setAlerts((curr) => {
      const next = { ...curr };
      if (next[id]) {
        delete next[id];
        toast(`${label} alert disarmed`, { duration: 1500 });
      } else {
        next[id] = { price, label, armed_at: Date.now() };
        try {
          sounds.click();
        } catch (e) {
          console.warn("[KeyLevels] click sound blocked:", e?.message || e);
        }
        toast.success(`${label} alert ARMED @ ${price.toFixed(2)}`, { duration: 2000 });
      }
      localStorage.setItem(LS_ALERTS, JSON.stringify(next));
      return next;
    });
  }, []);

  if (!ctx) return null;

  const cur = currentPrice || ctx.current;
  const ticks = (lvl) => (cur && lvl ? Math.round((cur - lvl) * 4) : null);

  const colorFor = (lvl) => {
    const t = ticks(lvl);
    if (t === null) return "#9ca3af";
    if (Math.abs(t) < 20) return "#FFCC00";
    return t > 0 ? "#FF3B30" : "#34C759";
  };

  const armedCount = Object.keys(alerts).length;

  const levels = [
    { id: "pdh",  label: "PDH",   price: ctx.prior_high  },
    { id: "pdl",  label: "PDL",   price: ctx.prior_low   },
    { id: "pdc",  label: "PDC",   price: ctx.prior_close },
    { id: "dayh", label: "DAY H", price: ctx.today_high  },
    { id: "dayl", label: "DAY L", price: ctx.today_low   },
    { id: "open", label: "OPEN",  price: ctx.today_open  },
  ];

  return (
    <div
      className="flex items-center gap-2 px-3 py-1.5 border border-white/10 bg-[#0A0A0A]/95 rounded-sm overflow-x-auto"
      data-testid="key-levels-strip"
    >
      <span className="text-[0.5rem] font-black tracking-wider text-zinc-500 shrink-0">
        KEY LEVELS
        {armedCount > 0 && (
          <span className="ml-1.5 px-1 py-0.5 rounded-sm bg-[#FFCC00]/20 text-[#FFCC00]" data-testid="alerts-count">
            {armedCount}♪
          </span>
        )}
      </span>
      {levels.map((l) => (
        <Pill
          key={l.id}
          id={l.id}
          label={l.label}
          price={l.price}
          ticks={ticks(l.price)}
          color={colorFor(l.price)}
          alerted={!!alerts[l.id]}
          flashing={!!flashing[l.id]}
          onToggle={toggleAlert}
          testId={`kl-${l.id}`}
        />
      ))}
    </div>
  );
}
