import React, { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { Radio } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const fmtP = (v) => (typeof v === "number" ? v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : "—");
const fmtV = (v) => (v >= 1000 ? `${(v / 1000).toFixed(1)}k` : Math.round(v).toString());

// Buy fraction estimate: where the close landed inside the bar's range
const buyFrac = (c) => {
  const range = c.high - c.low;
  if (range <= 0) return c.close >= c.open ? 1 : 0;
  return (c.close - c.low) / range;
};

const enrich = (candles) =>
  candles.map((c) => {
    const f = buyFrac(c);
    const buy = c.volume * f;
    const sell = c.volume - buy;
    return { ...c, buy, sell, delta: buy - sell };
  });

// ---------- DELTA ----------
const DeltaView = ({ candles }) => {
  const bars = candles.slice(-40);
  const maxAbs = Math.max(1, ...bars.map((b) => Math.abs(b.delta)));
  let cum = 0;
  const cumSeries = bars.map((b) => (cum += b.delta));
  const cumMax = Math.max(1, ...cumSeries.map(Math.abs));
  const totalDelta = cumSeries[cumSeries.length - 1] || 0;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[0.6rem] font-mono text-zinc-500">PER-BAR DELTA (1m × {bars.length})</span>
        <span className={`text-xs font-mono font-bold ${totalDelta >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`} data-testid="delta-cumulative">
          CUM Δ {totalDelta >= 0 ? "+" : ""}{fmtV(totalDelta)}
        </span>
      </div>
      <div className="relative h-40 flex items-center gap-[2px]">
        <div className="absolute inset-x-0 top-1/2 border-t border-white/10" />
        {bars.map((b, i) => {
          const h = Math.max(2, (Math.abs(b.delta) / maxAbs) * 72);
          const up = b.delta >= 0;
          return (
            <div key={b.time} className="relative flex-1 h-full">
              <div
                className={`absolute left-0 right-0 ${up ? "bg-[#34C759]" : "bg-[#FF3B30]"} rounded-[1px] opacity-80`}
                style={up ? { bottom: "50%", height: `${h}px` } : { top: "50%", height: `${h}px` }}
              />
              <div
                className="absolute w-1 h-1 rounded-full bg-[#007AFF] left-1/2 -translate-x-1/2"
                style={{ top: `${50 - (cumSeries[i] / cumMax) * 45}%` }}
              />
            </div>
          );
        })}
      </div>
      <p className="mt-1 text-[0.55rem] text-zinc-600">Green/red = bar delta · blue dots = cumulative delta path</p>
    </div>
  );
};

// ---------- VOLUME PROFILE ----------
const VolumeProfileView = ({ candles, lastClose }) => {
  const { rows, maxVol, pocIdx } = useMemo(() => {
    const lo = Math.min(...candles.map((c) => c.low));
    const hi = Math.max(...candles.map((c) => c.high));
    const N = 22;
    const step = (hi - lo) / N || 1;
    const buckets = Array.from({ length: N }, (_, i) => ({ price: hi - step * (i + 0.5), buy: 0, sell: 0 }));
    candles.forEach((c) => {
      const f = buyFrac(c);
      const first = Math.max(0, Math.min(N - 1, Math.floor((hi - c.high) / step)));
      const last = Math.max(0, Math.min(N - 1, Math.floor((hi - c.low) / step)));
      const span = last - first + 1;
      for (let i = first; i <= last; i++) {
        buckets[i].buy += (c.volume * f) / span;
        buckets[i].sell += (c.volume * (1 - f)) / span;
      }
    });
    const vols = buckets.map((b) => b.buy + b.sell);
    return { rows: buckets, maxVol: Math.max(1, ...vols), pocIdx: vols.indexOf(Math.max(...vols)) };
  }, [candles]);

  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <span className="text-[0.6rem] font-mono text-zinc-500">VOLUME AT PRICE (1m × {candles.length})</span>
        <span className="text-[0.6rem] font-mono text-[#FFCC00]" data-testid="vp-poc">POC {fmtP(rows[pocIdx]?.price)}</span>
      </div>
      <div className="space-y-[2px]">
        {rows.map((r, i) => {
          const total = r.buy + r.sell;
          const w = (total / maxVol) * 100;
          const isPoc = i === pocIdx;
          const isCur = lastClose >= r.price - Math.abs(rows[0].price - rows[1].price) / 2 && lastClose < r.price + Math.abs(rows[0].price - rows[1].price) / 2;
          return (
            <div key={r.price} className={`flex items-center gap-2 ${isPoc ? "bg-[#FFCC00]/5" : ""}`}>
              <span className={`w-16 shrink-0 text-right text-[0.55rem] font-mono ${isCur ? "text-[#007AFF] font-bold" : isPoc ? "text-[#FFCC00]" : "text-zinc-500"}`}>
                {fmtP(r.price)}
              </span>
              <div className="flex-1 h-2.5 flex rounded-[1px] overflow-hidden bg-white/[0.03]">
                <div className="bg-[#34C759]/70" style={{ width: `${(r.buy / total || 0) * w}%` }} />
                <div className="bg-[#FF3B30]/70" style={{ width: `${(r.sell / total || 0) * w}%` }} />
              </div>
              <span className="w-10 shrink-0 text-[0.5rem] font-mono text-zinc-600">{fmtV(total)}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ---------- FOOTPRINT ----------
const FootprintView = ({ candles }) => {
  const cols = candles.slice(-8);
  return (
    <div>
      <span className="block text-[0.6rem] font-mono text-zinc-500 mb-2">SELL × BUY PER PRICE CELL (last {cols.length} bars)</span>
      <div className="flex gap-1.5 overflow-x-auto pb-1">
        {cols.map((c) => {
          const f = buyFrac(c);
          const cells = 5;
          const step = (c.high - c.low) / cells || 0.25;
          const rows = Array.from({ length: cells }, (_, i) => {
            const cellTop = c.high - step * i;
            // weight volume toward the close location
            const closeCell = Math.max(0, Math.min(cells - 1, Math.floor((c.high - c.close) / step)));
            const weight = 1 + (i === closeCell ? 1.5 : 0);
            return { price: cellTop - step / 2, weight };
          });
          const wSum = rows.reduce((s, r) => s + r.weight, 0);
          const up = c.close >= c.open;
          return (
            <div key={c.time} className="shrink-0 w-[76px]">
              <div className={`text-center text-[0.5rem] font-mono mb-1 ${up ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                {new Date(c.time * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
              </div>
              <div className="space-y-[2px]">
                {rows.map((r) => {
                  const vol = (c.volume * r.weight) / wSum;
                  const buy = Math.round(vol * f);
                  const sell = Math.round(vol - buy);
                  const dom = buy > sell;
                  return (
                    <div
                      key={r.price}
                      className={`px-1 py-[3px] rounded-[1px] text-center text-[0.5rem] font-mono border ${
                        dom ? "bg-[#34C759]/10 border-[#34C759]/25 text-[#34C759]" : "bg-[#FF3B30]/10 border-[#FF3B30]/25 text-[#FF3B30]"
                      }`}
                    >
                      <span className="text-[#FF3B30]/90">{fmtV(sell)}</span>
                      <span className="text-zinc-600 mx-0.5">×</span>
                      <span className="text-[#34C759]/90">{fmtV(buy)}</span>
                    </div>
                  );
                })}
              </div>
              <div className={`text-center text-[0.5rem] font-mono mt-1 ${c.delta >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                Δ {c.delta >= 0 ? "+" : ""}{fmtV(c.delta)}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

const TITLES = { footprint: "FOOTPRINT", delta: "DELTA", volume_profile: "VOLUME PROFILE" };

/** Order-flow style chart views computed from the live MNQ 1m candle feed. */
export default function OrderFlowChart({ mode }) {
  const [candles, setCandles] = useState([]);
  const [lastClose, setLastClose] = useState(null);

  useEffect(() => {
    let alive = true;
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/operator/candles?timeframe=1m&count=60`);
        if (alive && Array.isArray(data.candles)) {
          setCandles(enrich(data.candles));
          setLastClose(data.last_close);
        }
      } catch { /* keep last */ }
    };
    load();
    const t = setInterval(load, 10000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  return (
    <div className="col-span-1 md:col-span-4 lg:col-span-12 bg-[#0D0D0F] border border-white/10 rounded-sm p-3" data-testid="orderflow-chart">
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <span className="flex items-center gap-2 text-xs font-black tracking-wider text-white">
          <Radio className="w-3.5 h-3.5 text-[#34C759] animate-pulse" />
          MNQ {TITLES[mode] || "CHART"}
        </span>
        <span className="font-mono text-sm font-bold text-white" data-testid="orderflow-price">{fmtP(lastClose)}</span>
      </div>
      {candles.length === 0 ? (
        <div className="h-40 flex items-center justify-center text-xs text-zinc-500">Loading live candles…</div>
      ) : mode === "delta" ? (
        <DeltaView candles={candles} />
      ) : mode === "volume_profile" ? (
        <VolumeProfileView candles={candles} lastClose={lastClose} />
      ) : (
        <FootprintView candles={candles} />
      )}
      <p className="mt-2 text-[0.5rem] text-zinc-700">Approximated from live OHLCV (Yahoo NQ=F) — not exchange bid/ask order-flow data.</p>
    </div>
  );
}
