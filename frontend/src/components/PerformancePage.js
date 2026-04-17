import React, { useState, useEffect } from "react";
import axios from "axios";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
  CartesianGrid,
} from "recharts";
import {
  TrendingUp,
  TrendingDown,
  Zap,
  Trophy,
  Target,
  Shield,
  BarChart3,
  Clock,
  Activity,
  ChevronRight,
  ExternalLink,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const formatPrice = (p) =>
  typeof p === "number"
    ? p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : "0.00";

// Custom tooltip for chart
const ChartTooltip = ({ active, payload, label }) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-[#1A1A1A] border border-white/20 rounded-sm px-3 py-2">
        <p className="text-xs text-zinc-400 mb-1">{label}</p>
        <p className={`text-sm font-mono font-bold ${payload[0].value >= 0 ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
          {payload[0].value >= 0 ? "+" : ""}{payload[0].value} pts
        </p>
      </div>
    );
  }
  return null;
};

// Hero Stats
const HeroStats = ({ overview }) => {
  const stats = [
    {
      label: "Win Rate",
      value: `${overview.win_rate}%`,
      color: overview.win_rate >= 60 ? "text-[#34C759]" : "text-[#FFCC00]",
      icon: Trophy,
      glow: overview.win_rate >= 60,
    },
    {
      label: "Total P&L",
      value: `+${overview.total_pnl_points} pts`,
      color: overview.total_pnl_points >= 0 ? "text-[#34C759]" : "text-[#FF3B30]",
      icon: TrendingUp,
      glow: true,
    },
    {
      label: "Avg R:R",
      value: `${overview.avg_rr}:1`,
      color: "text-[#007AFF]",
      icon: Target,
      glow: false,
    },
    {
      label: "Best Streak",
      value: `${overview.best_win_streak} wins`,
      color: "text-[#FFCC00]",
      icon: Zap,
      glow: false,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((stat, i) => {
        const Icon = stat.icon;
        return (
          <div
            key={i}
            className="relative bg-[#121212] border border-white/10 rounded-sm p-5 flex flex-col items-center text-center overflow-hidden group hover:border-white/20 transition-colors"
            data-testid={`hero-stat-${stat.label.toLowerCase().replace(/\s/g, "-")}`}
          >
            <Icon className={`w-5 h-5 mb-2 ${stat.color} opacity-60`} />
            <span className="text-xs font-bold uppercase tracking-[0.15em] text-zinc-500 mb-1">
              {stat.label}
            </span>
            <span className={`text-2xl md:text-3xl font-mono font-bold tracking-tight ${stat.color} ${stat.glow ? "glow-green" : ""}`}>
              {stat.value}
            </span>
          </div>
        );
      })}
    </div>
  );
};

// P&L Curve Chart
const PnLCurve = ({ data }) => {
  if (!data || data.length === 0) return null;

  // Aggregate by date
  const byDate = {};
  data.forEach((d) => {
    byDate[d.date] = d.pnl;
  });
  const chartData = Object.entries(byDate).map(([date, pnl]) => ({
    date: date.slice(5), // MM-DD
    pnl,
  }));

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-4" data-testid="pnl-curve-chart">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-xs font-bold uppercase tracking-[0.15em] text-zinc-500 flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-[#007AFF]" />
          Equity Curve (Points)
        </h3>
        <span className="text-xs text-zinc-600">{chartData.length} days</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <AreaChart data={chartData} margin={{ top: 5, right: 5, bottom: 5, left: 5 }}>
          <defs>
            <linearGradient id="pnlGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor="#34C759" stopOpacity={0.3} />
              <stop offset="95%" stopColor="#34C759" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="date"
            tick={{ fill: "#71717a", fontSize: 10, fontFamily: "JetBrains Mono" }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            tickLine={false}
          />
          <YAxis
            tick={{ fill: "#71717a", fontSize: 10, fontFamily: "JetBrains Mono" }}
            axisLine={{ stroke: "rgba(255,255,255,0.1)" }}
            tickLine={false}
            tickFormatter={(v) => `${v >= 0 ? "+" : ""}${v}`}
          />
          <Tooltip content={<ChartTooltip />} />
          <Area
            type="monotone"
            dataKey="pnl"
            stroke="#34C759"
            strokeWidth={2}
            fill="url(#pnlGradient)"
            dot={false}
            activeDot={{ r: 4, fill: "#34C759", stroke: "#0A0A0A", strokeWidth: 2 }}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
};

// Win/Loss breakdown
const WinLossBar = ({ wins, losses }) => {
  const total = wins + losses;
  if (total === 0) return null;
  const winPct = (wins / total) * 100;

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm p-4" data-testid="win-loss-bar">
      <h3 className="text-xs font-bold uppercase tracking-[0.15em] text-zinc-500 mb-3">
        Signal Distribution
      </h3>
      <div className="flex items-center gap-3 mb-2">
        <div className="h-3 flex-1 bg-[#FF3B30]/20 rounded-full overflow-hidden">
          <div
            className="h-full bg-[#34C759] rounded-full transition-all duration-700"
            style={{ width: `${winPct}%` }}
          />
        </div>
      </div>
      <div className="flex justify-between text-xs font-mono">
        <span className="text-[#34C759]">{wins}W ({winPct.toFixed(0)}%)</span>
        <span className="text-[#FF3B30]">{losses}L ({(100 - winPct).toFixed(0)}%)</span>
      </div>
    </div>
  );
};

// Recent Signals
const RecentSignals = ({ signals }) => (
  <div className="bg-[#121212] border border-white/10 rounded-sm" data-testid="recent-signals">
    <div className="p-4 border-b border-white/10">
      <h3 className="text-xs font-bold uppercase tracking-[0.15em] text-zinc-500 flex items-center gap-2">
        <Activity className="w-4 h-4 text-[#007AFF]" />
        Recent Signals
      </h3>
    </div>
    <div className="divide-y divide-white/5">
      {signals.map((sig) => {
        const isLong = sig.side === "long";
        return (
          <div
            key={sig.id}
            className="px-4 py-3 flex items-center justify-between hover:bg-white/[0.02] transition-colors"
            data-testid={`public-signal-${sig.id}`}
          >
            <div className="flex items-center gap-3">
              {isLong ? (
                <div className="w-8 h-8 rounded-sm bg-[#34C759]/10 flex items-center justify-center">
                  <TrendingUp className="w-4 h-4 text-[#34C759]" />
                </div>
              ) : (
                <div className="w-8 h-8 rounded-sm bg-[#FF3B30]/10 flex items-center justify-center">
                  <TrendingDown className="w-4 h-4 text-[#FF3B30]" />
                </div>
              )}
              <div>
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-bold ${isLong ? "text-[#34C759]" : "text-[#FF3B30]"}`}>
                    {sig.side.toUpperCase()} {sig.symbol}
                  </span>
                  <span className="text-[0.6rem] text-zinc-600 font-mono">
                    Score {sig.confluence_score}/3
                  </span>
                </div>
                <span className="text-xs text-zinc-600 font-mono">
                  Entry: ${formatPrice(sig.entry_price)}
                </span>
              </div>
            </div>

            <div className="text-right">
              {sig.outcome ? (
                <span className={`text-sm font-mono font-bold ${
                  sig.outcome === "win" ? "text-[#34C759]" : "text-[#FF3B30]"
                }`}>
                  {sig.pnl_points >= 0 ? "+" : ""}{sig.pnl_points} pts
                </span>
              ) : (
                <span className="text-xs px-2 py-0.5 bg-[#007AFF]/20 text-[#007AFF] rounded font-bold">
                  ACTIVE
                </span>
              )}
              <div className="text-[0.6rem] text-zinc-600 mt-0.5">
                {sig.created_at ? new Date(sig.created_at).toLocaleDateString() : ""}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

// ===================== Main Performance Page =====================
const PerformancePage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPerformance = async () => {
      try {
        // Seed demo data first (idempotent)
        await axios.post(`${API}/public/seed-demo`);
        const res = await axios.get(`${API}/public/performance`);
        setData(res.data);
      } catch (e) {
        console.error("Error fetching performance:", e);
      }
      setLoading(false);
    };
    fetchPerformance();
    const interval = setInterval(async () => {
      try {
        const res = await axios.get(`${API}/public/performance`);
        setData(res.data);
      } catch (e) { /* silent */ }
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="text-center">
          <Zap className="w-10 h-10 text-[#FFCC00] mx-auto mb-3 animate-pulse" />
          <p className="text-zinc-500 text-sm">Loading performance data...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <p className="text-zinc-500">Failed to load data.</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="performance-page">
      {/* Header */}
      <header className="border-b border-white/10 bg-[#0A0A0A]/90 backdrop-blur-xl sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Zap className="w-6 h-6 text-[#FFCC00]" />
            <h1 className="text-lg font-black tracking-tight text-white">
              MNQ STACK SIGNALS
            </h1>
            <span className="hidden md:inline text-xs px-2 py-0.5 bg-[#34C759]/20 text-[#34C759] rounded font-bold uppercase">
              Live
            </span>
          </div>
          <a
            href="/"
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#007AFF] text-white text-xs font-bold rounded-sm hover:bg-[#3395FF] transition-colors"
            data-testid="back-to-dashboard"
          >
            Dashboard
            <ChevronRight className="w-3.5 h-3.5" />
          </a>
        </div>
      </header>

      <main className="max-w-6xl mx-auto px-4 py-6 space-y-6">
        {/* Hero tagline */}
        <div className="text-center py-6">
          <h2 className="text-2xl md:text-4xl font-black tracking-tighter text-white mb-2">
            Verified Signal Performance
          </h2>
          <p className="text-zinc-500 text-sm max-w-lg mx-auto">
            Real-time MNQ futures signals powered by confluence scoring.
            Every trade logged. Every result tracked.
          </p>
        </div>

        {/* Hero Stats */}
        <HeroStats overview={data.overview} />

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="lg:col-span-2">
            <PnLCurve data={data.pnl_curve} />
          </div>
          <div className="space-y-4">
            <WinLossBar wins={data.overview.wins} losses={data.overview.losses} />

            {/* Extra stats */}
            <div className="bg-[#121212] border border-white/10 rounded-sm p-4 space-y-3">
              <h3 className="text-xs font-bold uppercase tracking-[0.15em] text-zinc-500">
                Detailed Metrics
              </h3>
              <div className="space-y-2">
                {[
                  ["Total Signals", data.overview.total_signals],
                  ["Closed", data.overview.closed_signals],
                  ["Active", data.overview.active_signals],
                  ["Avg Win", `+${data.overview.avg_win_points} pts`],
                  ["Avg Loss", `-${data.overview.avg_loss_points} pts`],
                ].map(([label, val], i) => (
                  <div key={i} className="flex justify-between text-sm">
                    <span className="text-zinc-500">{label}</span>
                    <span className="font-mono text-white">{val}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Recent Signals */}
        <RecentSignals signals={data.recent_signals} />

        {/* CTA */}
        <div className="text-center py-8 border-t border-white/10">
          <p className="text-zinc-500 text-xs mb-3 uppercase tracking-widest">
            Powered by MNQ Stack Signal Engine
          </p>
          <div className="flex items-center justify-center gap-3 text-zinc-600 text-xs">
            <span className="flex items-center gap-1">
              <Shield className="w-3 h-3" /> Kill Switch Protected
            </span>
            <span className="flex items-center gap-1">
              <Clock className="w-3 h-3" /> Real-Time Updates
            </span>
            <span className="flex items-center gap-1">
              <Activity className="w-3 h-3" /> 24/7 Monitoring
            </span>
          </div>
        </div>
      </main>
    </div>
  );
};

export default PerformancePage;
