import React, { useEffect, useRef, useState } from "react";
import { createChart, CandlestickSeries, LineSeries, HistogramSeries } from "lightweight-charts";
import axios from "axios";
import { BarChart3 } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const TIMEFRAMES = ["1m", "5m", "15m"];

export default function LiveChart() {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef({});
  const [tf, setTf] = useState("1m");
  const [last, setLast] = useState(null);

  // Build chart once
  useEffect(() => {
    if (!containerRef.current) return;
    const chart = createChart(containerRef.current, {
      layout: {
        background: { color: "#0A0A0A" },
        textColor: "#9ca3af",
        fontFamily: "ui-monospace, SFMono-Regular, monospace",
      },
      grid: {
        vertLines: { color: "rgba(255,255,255,0.04)" },
        horzLines: { color: "rgba(255,255,255,0.04)" },
      },
      localization: {
        locale: "en-US",
        dateFormat: "yyyy-MM-dd",
        timeFormatter: (t) => {
          const d = new Date(t * 1000);
          const h = d.getUTCHours().toString().padStart(2, "0");
          const m = d.getUTCMinutes().toString().padStart(2, "0");
          return `${h}:${m}`;
        },
      },
      timeScale: {
        timeVisible: true,
        secondsVisible: false,
        borderColor: "rgba(255,255,255,0.08)",
        tickMarkFormatter: (t) => {
          const d = new Date(t * 1000);
          const h = d.getUTCHours().toString().padStart(2, "0");
          const m = d.getUTCMinutes().toString().padStart(2, "0");
          return `${h}:${m}`;
        },
      },
      rightPriceScale: { borderColor: "rgba(255,255,255,0.08)" },
      crosshair: { mode: 1 },
      autoSize: true,
    });

    const candle = chart.addSeries(CandlestickSeries, {
      upColor: "#34C759",
      downColor: "#FF3B30",
      borderUpColor: "#34C759",
      borderDownColor: "#FF3B30",
      wickUpColor: "#34C759",
      wickDownColor: "#FF3B30",
    });
    const ema9 = chart.addSeries(LineSeries, { color: "#FFCC00", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const ema21 = chart.addSeries(LineSeries, { color: "#007AFF", lineWidth: 1, priceLineVisible: false, lastValueVisible: false });
    const vwap = chart.addSeries(LineSeries, { color: "#a855f7", lineWidth: 1, lineStyle: 2, priceLineVisible: false, lastValueVisible: false });

    const volume = chart.addSeries(HistogramSeries, {
      color: "rgba(52,199,89,0.35)",
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chart.priceScale("vol").applyOptions({ scaleMargins: { top: 0.85, bottom: 0 } });

    chartRef.current = chart;
    seriesRef.current = { candle, ema9, ema21, vwap, volume };

    return () => chart.remove();
  }, []);

  // Load data on timeframe change + refresh every 15s
  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const { data } = await axios.get(`${API}/operator/candles`, { params: { timeframe: tf, count: 180 } });
        if (cancelled || !seriesRef.current.candle) return;

        seriesRef.current.candle.setData(data.candles);
        seriesRef.current.ema9.setData(data.ema9);
        seriesRef.current.ema21.setData(data.ema21);
        seriesRef.current.vwap.setData(data.vwap);
        seriesRef.current.volume.setData(
          data.candles.map((c) => ({
            time: c.time,
            value: c.volume,
            color: c.close >= c.open ? "rgba(52,199,89,0.45)" : "rgba(255,59,48,0.45)",
          })),
        );
        setLast(data.last_close);
      } catch (e) {
        // silent — chart keeps last frame
      }
    };
    load();
    const id = setInterval(load, 15000);
    return () => { cancelled = true; clearInterval(id); };
  }, [tf]);

  return (
    <div className="relative w-full h-full bg-[#0A0A0A] border border-white/10 rounded-sm overflow-hidden" data-testid="live-chart">
      {/* Header row */}
      <div className="absolute top-0 left-0 right-0 h-9 px-3 flex items-center justify-between z-10 border-b border-white/5 bg-[#0A0A0A]/80 backdrop-blur-sm">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-3.5 h-3.5 text-[#34C759]" />
          <span className="text-[0.65rem] font-black tracking-wider text-white">MNQ</span>
          {last && <span className="text-[0.65rem] font-mono text-zinc-400">{last.toFixed(2)}</span>}
        </div>
        <div className="flex items-center gap-3">
          {/* Indicator legend */}
          <div className="hidden md:flex items-center gap-2 text-[0.55rem] font-mono">
            <span className="text-[#FFCC00]">EMA9</span>
            <span className="text-[#007AFF]">EMA21</span>
            <span className="text-[#a855f7]">VWAP</span>
          </div>
          {/* TF switcher */}
          <div className="flex gap-1">
            {TIMEFRAMES.map((t) => (
              <button
                key={t}
                onClick={() => setTf(t)}
                data-testid={`chart-tf-${t}`}
                className={`px-2 py-0.5 text-[0.6rem] font-bold rounded-sm transition-colors ${
                  tf === t ? "bg-[#34C759] text-black" : "bg-white/5 text-zinc-400 hover:bg-white/10"
                }`}
              >
                {t}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Watermark logo (subtle, bottom-right) */}
      <div className="absolute bottom-2 right-12 z-10 pointer-events-none select-none opacity-30">
        <span className="text-[0.55rem] font-black tracking-widest text-white/40">MNQ • SCALP STACKS</span>
      </div>

      <div ref={containerRef} className="absolute inset-0 top-9" />
    </div>
  );
}
