import React, { useState, useEffect } from "react";
import axios from "axios";
import { Trophy, Users, Flame, TrendingUp, Crown, Star, Medal } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Leaderboard = () => {
  const [data, setData] = useState(null);

  useEffect(() => {
    axios.get(`${API}/public/leaderboard`).then(r => setData(r.data)).catch(() => {});
  }, []);

  if (!data) return null;

  const tierColors = { elite: "text-[#34C759]", pro: "text-[#FFCC00]", free: "text-[#007AFF]" };
  const rankIcons = [Crown, Star, Medal];

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm overflow-hidden" data-testid="leaderboard">
      {/* Header */}
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <h3 className="text-xs font-bold uppercase tracking-[0.15em] text-zinc-500 flex items-center gap-2">
          <Trophy className="w-4 h-4 text-[#FFCC00]" /> Community Leaderboard
        </h3>
        <span className="text-xs text-zinc-600 flex items-center gap-1">
          <Users className="w-3 h-3" /> {data.total_subscribers} traders
        </span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 divide-y md:divide-y-0 md:divide-x divide-white/5">
        {/* Top Referrers */}
        <div className="p-4">
          <h4 className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-500 mb-3 flex items-center gap-1">
            <Users className="w-3 h-3" /> Top Referrers
          </h4>
          {data.top_referrers.length === 0 ? (
            <p className="text-xs text-zinc-600 text-center py-4">Be the first to refer a friend!</p>
          ) : (
            <div className="space-y-2">
              {data.top_referrers.slice(0, 5).map((r, i) => {
                const RankIcon = rankIcons[i] || Star;
                return (
                  <div key={r.name || `referrer-${i}`} className="flex items-center justify-between p-2 bg-white/[0.03] rounded-sm" data-testid={`referrer-${i}`}>
                    <div className="flex items-center gap-2">
                      <RankIcon className={`w-4 h-4 ${i === 0 ? "text-[#FFCC00]" : i === 1 ? "text-zinc-300" : "text-[#CD7F32]"}`} />
                      <span className="text-sm text-white font-semibold">{r.name}</span>
                      <span className={`text-[0.55rem] px-1 py-0.5 rounded ${tierColors[r.tier] || "text-zinc-500"} bg-white/5`}>
                        {r.tier?.toUpperCase()}
                      </span>
                    </div>
                    <span className="text-sm font-mono font-bold text-[#FFCC00]">{r.referrals}</span>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Monthly Performance */}
        <div className="p-4">
          <h4 className="text-[0.65rem] font-bold uppercase tracking-wider text-zinc-500 mb-3 flex items-center gap-1">
            <Flame className="w-3 h-3" /> This Month
          </h4>
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-white/[0.03] rounded-sm text-center">
              <span className="text-[0.55rem] text-zinc-500 block uppercase">Signals</span>
              <span className="text-xl font-mono font-bold text-white">{data.month_stats?.signals || 0}</span>
            </div>
            <div className="p-3 bg-white/[0.03] rounded-sm text-center">
              <span className="text-[0.55rem] text-zinc-500 block uppercase">Win Rate</span>
              <span className="text-xl font-mono font-bold text-[#34C759]">{data.month_stats?.win_rate || 0}%</span>
            </div>
            <div className="p-3 bg-white/[0.03] rounded-sm text-center">
              <span className="text-[0.55rem] text-zinc-500 block uppercase">P&L</span>
              <span className={`text-xl font-mono font-bold ${(data.month_stats?.pnl_points || 0) >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                {(data.month_stats?.pnl_points || 0) >= 0 ? "+" : ""}{data.month_stats?.pnl_points || 0}
              </span>
            </div>
            <div className="p-3 bg-white/[0.03] rounded-sm text-center">
              <span className="text-[0.55rem] text-zinc-500 block uppercase">Best Streak</span>
              <span className="text-xl font-mono font-bold text-[#FFCC00]">{data.best_win_streak || 0}W</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Leaderboard;
