import React, { useEffect, useState } from "react";
import axios from "axios";
import { Radio } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

/** Public proof strip — last 10 resolved signals, wins AND losses, posted live. */
const WinStreakStrip = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    axios.get(`${API}/signals/recent-results?limit=10`).then((r) => setData(r.data)).catch(() => {});
  }, []);

  if (!data || (data.results || []).length < 3) return null;
  const { results, wins, losses, win_rate, net_points } = data;

  return (
    <section className="py-6 md:py-8 px-5 md:px-6 bg-[#0D0D0D] border-y border-white/5" data-testid="win-streak-strip">
      <div className="max-w-5xl mx-auto">
        <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
          <span className="flex items-center gap-2 text-[0.65rem] md:text-xs font-black tracking-[0.2em] text-zinc-400 uppercase">
            <Radio className="w-3.5 h-3.5 text-[#34C759] animate-pulse" />
            Last {results.length} signals — posted live, wins &amp; losses
          </span>
          <span className="text-[0.65rem] md:text-xs font-mono text-zinc-500" data-testid="win-streak-summary">
            <span className="text-[#34C759] font-bold">{wins}W</span> / <span className="text-[#FF3B30] font-bold">{losses}L</span>
            {" · "}{win_rate}% win rate{" · "}
            <span className={net_points >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}>
              {net_points >= 0 ? "+" : ""}{net_points} pts
            </span>
          </span>
        </div>
        <div className="flex gap-1.5 overflow-x-auto pb-1" data-testid="win-streak-chips">
          {results.map((r, i) => {
            const win = r.outcome === "win";
            return (
              <div
                key={`${r.created_at}-${i}`}
                className={`shrink-0 px-2.5 py-1.5 rounded-sm border text-center ${
                  win ? "border-[#34C759]/40 bg-[#34C759]/10" : "border-[#FF3B30]/40 bg-[#FF3B30]/10"
                }`}
              >
                <span className={`block text-sm font-black ${win ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                  {win ? "W" : "L"}
                </span>
                <span className="block text-[0.55rem] font-mono text-zinc-400">
                  {(r.pnl_points ?? 0) >= 0 ? "+" : ""}{r.pnl_points ?? 0} pts
                </span>
              </div>
            );
          })}
        </div>
        <p className="mt-2 text-[0.5rem] text-zinc-700">
          Trading futures involves substantial risk of loss. Past performance is not indicative of future results.
        </p>
      </div>
    </section>
  );
};

export default WinStreakStrip;
