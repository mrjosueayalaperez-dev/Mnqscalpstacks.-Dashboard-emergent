import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { createChart, CandlestickSeries, LineSeries, ColorType, LineStyle } from "lightweight-charts";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

// Shift epochs so the time axis reads in ET (lightweight-charts renders UTC)
const etOffsetSec = () => {
  const now = new Date();
  const et = new Date(now.toLocaleString("en-US", { timeZone: "America/New_York" }));
  const utc = new Date(now.toLocaleString("en-US", { timeZone: "UTC" }));
  return Math.round((et - utc) / 1000);
};

const LINE_DEFS = [
  { key: "entry_price", title: "ENTRY", color: "#007AFF", style: LineStyle.Solid, width: 2 },
  { key: "stop_loss", title: "STOP", color: "#FF3B30", style: LineStyle.Dashed, width: 1 },
  { key: "tp1", title: "TP1", color: "#34C759", style: LineStyle.Dashed, width: 1 },
  { key: "tp2", title: "TP2", color: "#34C759", style: LineStyle.Dotted, width: 1 },
];

/** Native MNQ candle chart with the active signal's entry/stop/TP levels drawn as price lines. */
export const SignalChart = ({ interval = "1m" }) => {
  const holderRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef({});
  const priceLinesRef = useRef([]);
  const [signal, setSignal] = useState(null);

  useEffect(() => {
    const el = holderRef.current;
    if (!el) return undefined;
    const chart = createChart(el, {
      autoSize: true,
      localization: { locale: "en-US" },
      layout: {
        background: { type: ColorType.Solid, color: "#0A0A0A" },
        textColor: "#71717a",
        fontSize: 10,
        attributionLogo: false,
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      timeScale: { timeVisible: true, secondsVisible: false, borderColor: "rgba(255,255,255,0.1)" },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.1)" },
      crosshair: { horzLine: { labelBackgroundColor: "#182234" }, vertLine: { labelBackgroundColor: "#182234" } },
    });
    const candles = chart.addSeries(CandlestickSeries, {
      upColor: "#34C759", downColor: "#FF3B30",
      wickUpColor: "#34C759", wickDownColor: "#FF3B30",
      borderVisible: false,
    });
    const mkLine = (color) =>
      chart.addSeries(LineSeries, { color, lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false });
    seriesRef.current = { candles, ema9: mkLine("#FFCC00"), ema21: mkLine("#FFFFFF"), vwap: mkLine("#7dd3fc") };
    chartRef.current = chart;
    return () => { chart.remove(); chartRef.current = null; };
  }, []);

  // Candles + indicator lines
  useEffect(() => {
    let stop = false;
    let first = true;
    const off = etOffsetSec();
    const shift = (rows) => rows.map((r) => ({ ...r, time: r.time + off }));
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/operator/candles`, { params: { timeframe: interval, count: 200 } });
        if (stop || !data.candles?.length || !seriesRef.current.candles) return;
        seriesRef.current.candles.setData(shift(data.candles));
        seriesRef.current.ema9.setData(shift(data.ema9 || []));
        seriesRef.current.ema21.setData(shift(data.ema21 || []));
        seriesRef.current.vwap.setData(shift(data.vwap || []));
        if (first) {
          chartRef.current?.timeScale().fitContent();
          first = false;
        }
      } catch (e) {
        console.error("[SignalChart] candles load failed:", e?.message || e);
      }
    };
    load();
    const t = setInterval(load, 20000);
    return () => { stop = true; clearInterval(t); };
  }, [interval]);

  // Active signal levels (falls back to the latest punch)
  useEffect(() => {
    let stop = false;
    const load = async () => {
      try {
        const { data: act } = await axios.get(`${API}/signals`, { params: { limit: 1, status: "active" } });
        let sig = act?.[0];
        if (!sig) {
          const { data: last } = await axios.get(`${API}/signals`, { params: { limit: 1 } });
          sig = last?.[0];
        }
        if (!stop) setSignal(sig || null);
      } catch { /* next poll retries */ }
    };
    load();
    const t = setInterval(load, 12000);
    return () => { stop = true; clearInterval(t); };
  }, []);

  // Draw / redraw the price lines
  useEffect(() => {
    const candles = seriesRef.current.candles;
    if (!candles) return;
    priceLinesRef.current.forEach((l) => candles.removePriceLine(l));
    priceLinesRef.current = [];
    if (!signal) return;
    const tag = signal.status === "active" ? "" : " (LAST)";
    LINE_DEFS.forEach((d) => {
      const price = signal[d.key];
      if (typeof price !== "number" || !price) return;
      priceLinesRef.current.push(
        candles.createPriceLine({
          price,
          color: d.color,
          lineWidth: d.width,
          lineStyle: d.style,
          axisLabelVisible: true,
          title: d.key === "entry_price" ? `${d.title} ${signal.side?.toUpperCase() || ""}${tag}` : d.title,
        })
      );
    });
  }, [signal]);

  return (
    <div className="relative w-full h-full" data-testid={`signal-chart-${interval}`}>
      <div ref={holderRef} className="absolute inset-0" />
      {signal && (
        <div className="absolute top-1.5 left-1.5 z-10 pointer-events-none select-none px-1.5 py-0.5 rounded-sm bg-black/70 border border-white/10">
          <span className={`text-[0.55rem] font-black tracking-widest ${signal.side === "long" ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
            {signal.side?.toUpperCase()} {signal.entry_price} · {signal.status === "active" ? "ACTIVE" : `LAST · ${signal.status?.toUpperCase()}`}
          </span>
        </div>
      )}
    </div>
  );
};

export default SignalChart;
