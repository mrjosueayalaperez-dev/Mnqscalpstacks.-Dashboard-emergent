import React, { useState, useEffect, useCallback } from "react";
import axios from "axios";
import { toast, Toaster } from "sonner";
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
  Check,
  Star,
  Crown,
  Mail,
  User,
  Loader2,
  ArrowRight,
} from "lucide-react";
import Leaderboard from "@/components/Leaderboard";

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
      {stats.map((stat) => {
        const Icon = stat.icon;
        return (
          <div
            key={stat.label}
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

// ===================== Backtest Display (Public) =====================
const BacktestDisplay = ({ backtests }) => {
  if (!backtests || backtests.length === 0) return null;

  const bt = backtests[0]; // Show latest backtest

  const metrics = [
    { label: "Win Rate", value: `${bt.win_rate}%`, color: bt.win_rate >= 60 ? "text-[#34C759]" : "text-[#FFCC00]" },
    { label: "Profit Factor", value: bt.profit_factor.toFixed(2), color: bt.profit_factor >= 1.5 ? "text-[#34C759]" : "text-white" },
    { label: "Net Profit", value: `$${bt.net_profit?.toLocaleString()}`, color: bt.net_profit >= 0 ? "text-[#34C759]" : "text-[#FF3B30]" },
    { label: "Sharpe Ratio", value: bt.sharpe_ratio.toFixed(2), color: bt.sharpe_ratio >= 1.5 ? "text-[#007AFF]" : "text-white" },
    { label: "Max Drawdown", value: `${bt.max_drawdown_pct}%`, color: bt.max_drawdown_pct <= 10 ? "text-[#FFCC00]" : "text-[#FF3B30]" },
    { label: "Total Trades", value: bt.total_trades, color: "text-white" },
  ];

  const details = [
    ["Avg Trade", `$${bt.avg_trade?.toFixed(2)}`],
    ["Avg Win", `$${bt.avg_win?.toFixed(2)}`],
    ["Avg Loss", `$${bt.avg_loss?.toFixed(2)}`],
    ["Largest Win", `$${bt.largest_win?.toFixed(2)}`],
    ["Largest Loss", `$${bt.largest_loss?.toFixed(2)}`],
    ["Max Consec. Wins", bt.max_consecutive_wins],
    ["Max Consec. Losses", bt.max_consecutive_losses],
    ["Period", `${bt.period_start} to ${bt.period_end}`],
  ];

  return (
    <div className="bg-[#121212] border border-white/10 rounded-sm overflow-hidden" data-testid="backtest-display">
      <div className="p-4 border-b border-white/10 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-[#007AFF]" />
          <h3 className="text-sm font-bold text-white uppercase tracking-wider">
            Verified Backtest
          </h3>
          {bt.is_verified && (
            <span className="text-[0.6rem] px-2 py-0.5 bg-[#34C759]/20 text-[#34C759] rounded font-bold uppercase">
              Verified
            </span>
          )}
        </div>
        <span className="text-xs text-zinc-500">
          {bt.strategy_name} | {bt.symbol} {bt.timeframe}
        </span>
      </div>

      {/* Hero Metrics */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 divide-x divide-white/5">
        {metrics.map((m) => (
          <div key={m.label} className="p-4 text-center">
            <span className="text-[0.6rem] font-bold uppercase tracking-[0.15em] text-zinc-500 block mb-1">
              {m.label}
            </span>
            <span className={`text-xl md:text-2xl font-mono font-bold ${m.color}`}>
              {m.value}
            </span>
          </div>
        ))}
      </div>

      {/* Detail Grid */}
      <div className="border-t border-white/5 p-4">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {details.map(([label, value]) => (
            <div key={label} className="flex justify-between text-xs">
              <span className="text-zinc-500">{label}</span>
              <span className="font-mono text-white">{value}</span>
            </div>
          ))}
        </div>
        {bt.notes && (
          <p className="text-[0.65rem] text-zinc-500 mt-3 pt-3 border-t border-white/5">{bt.notes}</p>
        )}
      </div>
    </div>
  );
};

// ===================== Pricing Section =====================
const PricingSection = ({ subscriberCount }) => {
  const [tiers, setTiers] = useState([]);

  useEffect(() => {
    axios.get(`${API}/subscribers/tiers`).then((r) => setTiers(r.data)).catch(() => {});
  }, []);

  const tierIcons = { Free: Zap, Pro: Star, Elite: Crown };
  const tierColors = {
    Free: { border: "border-white/10", accent: "text-[#007AFF]", bg: "bg-white/5", btn: "bg-white/10 text-white hover:bg-white/20" },
    Pro: { border: "border-[#FFCC00]/30", accent: "text-[#FFCC00]", bg: "bg-[#FFCC00]/5", btn: "bg-[#FFCC00] text-black hover:bg-[#FFCC00]/80" },
    Elite: { border: "border-[#34C759]/30", accent: "text-[#34C759]", bg: "bg-[#34C759]/5", btn: "bg-[#34C759] text-black hover:bg-[#34C759]/80" },
  };

  return (
    <div className="py-8" data-testid="pricing-section">
      <div className="text-center mb-8">
        <h2 className="text-2xl md:text-3xl font-black tracking-tighter text-white mb-2">
          Get Real-Time Signals
        </h2>
        <p className="text-zinc-500 text-sm">
          Join {subscriberCount?.total || 0}+ traders already receiving MNQ Stack signals
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 max-w-4xl mx-auto">
        {tiers.map((tier) => {
          const Icon = tierIcons[tier.name] || Zap;
          const colors = tierColors[tier.name] || tierColors.Free;
          const isPopular = tier.name === "Pro";

          return (
            <div
              key={tier.id}
              className={`relative ${colors.bg} border ${colors.border} rounded-sm p-5 flex flex-col ${
                isPopular ? "ring-1 ring-[#FFCC00]/50" : ""
              }`}
              data-testid={`tier-${tier.id}`}
            >
              {isPopular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-[#FFCC00] text-black text-[0.6rem] font-black uppercase rounded-sm">
                  Most Popular
                </div>
              )}
              <div className="flex items-center gap-2 mb-3">
                <Icon className={`w-5 h-5 ${colors.accent}`} />
                <h3 className={`font-bold ${colors.accent}`}>{tier.name}</h3>
              </div>
              <div className="mb-4">
                <span className="text-3xl font-mono font-bold text-white">
                  {tier.price === 0 ? "Free" : `$${tier.price}`}
                </span>
                {tier.price > 0 && <span className="text-zinc-500 text-sm">/month</span>}
              </div>
              <ul className="space-y-2 flex-1 mb-4">
                {tier.features.map((f) => (
                  <li key={f} className="flex items-start gap-2 text-sm text-zinc-300">
                    <Check className={`w-4 h-4 mt-0.5 shrink-0 ${colors.accent}`} />
                    {f}
                  </li>
                ))}
              </ul>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ===================== Signup Form =====================
const SignupForm = ({ onSignup, onCheckout, loading, signedUp, discordInvite }) => {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [selectedTier, setSelectedTier] = useState("free");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!email) return;
    if (selectedTier === "free") {
      onSignup(email, name);
    } else {
      onCheckout(email, name, selectedTier);
    }
  };

  if (signedUp && discordInvite) {
    return (
      <div className="max-w-lg mx-auto text-center py-8 bg-[#121212] border border-[#34C759]/30 rounded-sm p-6" data-testid="signup-success">
        <div className="w-12 h-12 rounded-full bg-[#34C759]/20 flex items-center justify-center mx-auto mb-4">
          <Check className="w-6 h-6 text-[#34C759]" />
        </div>
        <h3 className="text-xl font-bold text-white mb-2">You're In!</h3>
        <p className="text-zinc-400 text-sm mb-4">Welcome to MNQ Stack Signals. Join the Discord to start receiving signals.</p>
        {discordInvite && !discordInvite.startsWith("REPLACE") ? (
          <a
            href={discordInvite}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-6 py-2.5 bg-[#5865F2] text-white font-bold rounded-sm hover:bg-[#4752c4] transition-colors"
            data-testid="discord-invite-link"
          >
            Join Discord <ExternalLink className="w-4 h-4" />
          </a>
        ) : (
          <p className="text-zinc-500 text-sm">Discord invite link will be shared soon!</p>
        )}
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto" data-testid="signup-form">
      <div className="bg-[#121212] border border-white/10 rounded-sm p-6">
        <h3 className="text-lg font-bold text-white mb-1 text-center">Start Receiving Signals</h3>
        <p className="text-zinc-500 text-xs text-center mb-5">Enter your email to get started</p>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="email"
              placeholder="your@email.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full pl-10 text-sm"
              data-testid="signup-email"
            />
          </div>
          <div className="relative">
            <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="text"
              placeholder="Name (optional)"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full pl-10 text-sm"
              data-testid="signup-name"
            />
          </div>

          {/* Tier Selection */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { id: "free", label: "Free", price: "$0" },
              { id: "pro", label: "Pro", price: "$49/mo" },
              { id: "elite", label: "Elite", price: "$149/mo" },
            ].map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setSelectedTier(t.id)}
                className={`p-2 rounded-sm text-center text-xs font-bold transition-all border ${
                  selectedTier === t.id
                    ? t.id === "elite"
                      ? "bg-[#34C759]/10 border-[#34C759]/50 text-[#34C759]"
                      : t.id === "pro"
                      ? "bg-[#FFCC00]/10 border-[#FFCC00]/50 text-[#FFCC00]"
                      : "bg-[#007AFF]/10 border-[#007AFF]/50 text-[#007AFF]"
                    : "bg-white/5 border-white/10 text-zinc-400 hover:border-white/20"
                }`}
                data-testid={`select-tier-${t.id}`}
              >
                <div>{t.label}</div>
                <div className="font-mono mt-0.5">{t.price}</div>
              </button>
            ))}
          </div>

          <button
            type="submit"
            disabled={loading || !email}
            className={`w-full py-2.5 rounded-sm font-bold text-sm transition-all flex items-center justify-center gap-2 ${
              selectedTier === "elite"
                ? "bg-[#34C759] text-black hover:bg-[#34C759]/80"
                : selectedTier === "pro"
                ? "bg-[#FFCC00] text-black hover:bg-[#FFCC00]/80"
                : "bg-[#007AFF] text-white hover:bg-[#3395FF]"
            } disabled:opacity-50`}
            data-testid="signup-submit-btn"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : selectedTier === "free" ? (
              <>Join Free <ArrowRight className="w-4 h-4" /></>
            ) : (
              <>Subscribe — ${selectedTier === "pro" ? "49" : "149"}/mo <ArrowRight className="w-4 h-4" /></>
            )}
          </button>
        </form>
      </div>
    </div>
  );
};

// ===================== Success Panel (post-payment) =====================
const SuccessPanel = ({ tier, discordInvite }) => (
  <div className="max-w-lg mx-auto text-center py-8 bg-[#121212] border border-[#34C759]/30 rounded-sm p-6" data-testid="payment-success">
    <div className="w-14 h-14 rounded-full bg-[#34C759]/20 flex items-center justify-center mx-auto mb-4">
      <Crown className="w-7 h-7 text-[#34C759]" />
    </div>
    <h3 className="text-2xl font-black text-white mb-2">Welcome to {tier?.title() || "Pro"}!</h3>
    <p className="text-zinc-400 text-sm mb-5">
      Your subscription is active. Join the exclusive Discord channel now.
    </p>
    {discordInvite && !discordInvite.startsWith("REPLACE") ? (
      <a
        href={discordInvite}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-2 px-6 py-3 bg-[#5865F2] text-white font-bold rounded-sm hover:bg-[#4752c4] transition-colors text-sm"
        data-testid="discord-invite-paid"
      >
        Join {tier?.title()} Discord <ExternalLink className="w-4 h-4" />
      </a>
    ) : (
      <p className="text-zinc-500 text-sm">Your Discord invite will be delivered shortly!</p>
    )}
  </div>
);

// ===================== Main Performance Page =====================
const PerformancePage = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [signupLoading, setSignupLoading] = useState(false);
  const [signedUp, setSignedUp] = useState(false);
  const [discordInvite, setDiscordInvite] = useState("");
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [paymentTier, setPaymentTier] = useState(null);
  const [subscriberCount, setSubscriberCount] = useState(null);
  const [backtests, setBacktests] = useState([]);

  // Check for returning from Stripe
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session_id");
    const tier = params.get("tier");

    if (sessionId) {
      // Poll payment status
      const pollStatus = async (attempts = 0) => {
        if (attempts >= 5) return;
        try {
          const res = await axios.get(`${API}/checkout/status/${sessionId}`);
          if (res.data.payment_status === "paid") {
            setPaymentSuccess(true);
            setPaymentTier(tier || "pro");
            setDiscordInvite(res.data.discord_invite || "");
            toast.success("Payment successful! Welcome aboard.");
          } else if (res.data.status !== "expired") {
            setTimeout(() => pollStatus(attempts + 1), 2000);
          }
        } catch (e) {
          console.error("Status poll error:", e);
        }
      };
      pollStatus();
      // Clean URL
      window.history.replaceState({}, "", "/performance");
    }
  }, []);

  useEffect(() => {
    const fetchPerformance = async () => {
      try {
        await axios.post(`${API}/public/seed-demo`);
        await axios.post(`${API}/backtests/seed-demo`);
        const [perfRes, countRes, btRes] = await Promise.all([
          axios.get(`${API}/public/performance`),
          axios.get(`${API}/subscribers/count`),
          axios.get(`${API}/public/backtests`),
        ]);
        setData(perfRes.data);
        setSubscriberCount(countRes.data);
        setBacktests(btRes.data);
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
      } catch (e) { console.error("Performance refresh error:", e); }
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSignup = async (email, name) => {
    setSignupLoading(true);
    try {
      const res = await axios.post(`${API}/subscribers`, { email, name, tier: "free" });
      setSignedUp(true);
      setDiscordInvite(res.data.discord_invite || "");
      toast.success("Welcome! You're signed up.");
    } catch (e) {
      toast.error("Signup failed. Please try again.");
    }
    setSignupLoading(false);
  };

  const handleCheckout = async (email, name, tier) => {
    setSignupLoading(true);
    try {
      await axios.post(`${API}/subscribers`, { email, name, tier });
      const res = await axios.post(`${API}/checkout/create`, {
        tier,
        origin_url: window.location.origin,
      });
      if (res.data.url) {
        window.location.href = res.data.url;
      } else {
        toast.error("No checkout URL returned");
        setSignupLoading(false);
      }
    } catch (e) {
      console.error("Checkout error:", e);
      toast.error("Checkout failed: " + (e.response?.data?.detail || e.message || "Unknown error"));
      setSignupLoading(false);
    }
  };

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
      <Toaster
        position="top-right"
        toastOptions={{
          style: { background: "#121212", border: "1px solid rgba(255,255,255,0.1)", color: "#fff" },
        }}
      />
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
                ].map(([label, val]) => (
                  <div key={label} className="flex justify-between text-sm">
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

        {/* Verified Backtest */}
        <BacktestDisplay backtests={backtests} />

        {/* Community Leaderboard */}
        <Leaderboard />

        {/* Pricing Section */}
        <PricingSection subscriberCount={subscriberCount} />

        {/* Signup / Success section */}
        {paymentSuccess ? (
          <SuccessPanel tier={paymentTier} discordInvite={discordInvite} />
        ) : (
          <SignupForm
            onSignup={handleSignup}
            onCheckout={handleCheckout}
            loading={signupLoading}
            signedUp={signedUp}
            discordInvite={discordInvite}
          />
        )}

        {/* Footer CTA */}
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
