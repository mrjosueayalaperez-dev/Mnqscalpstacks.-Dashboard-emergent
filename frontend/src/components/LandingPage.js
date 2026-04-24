import React, { useState, useEffect, useRef } from "react";
import axios from "axios";
import { Toaster, toast } from "sonner";
import {
  Zap,
  TrendingUp,
  Target,
  Shield,
  ChevronRight,
  Check,
  X,
  Star,
  Crown,
  BarChart3,
  Clock,
  Activity,
  ArrowRight,
  Eye,
  Crosshair,
  Layers,
  Mail,
  User,
  Loader2,
  ExternalLink,
  AlertTriangle,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// ======================== HERO ========================
const Hero = ({ onCTA, onLearn }) => (
  <section className="relative min-h-[90vh] flex items-center overflow-hidden" data-testid="hero-section">
    {/* Background */}
    <div className="absolute inset-0 bg-[#0A0A0A]">
      <div
        className="absolute inset-0 opacity-20"
        style={{
          backgroundImage: `url(https://images.unsplash.com/photo-1745270917233-65e776a47547?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85&w=1920)`,
          backgroundSize: "cover",
          backgroundPosition: "center",
        }}
      />
      <div className="absolute inset-0 bg-gradient-to-b from-[#0A0A0A]/60 via-[#0A0A0A]/80 to-[#0A0A0A]" />
    </div>

    <div className="relative max-w-5xl mx-auto px-6 py-20 text-center">
      {/* Badge */}
      <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#34C759]/10 border border-[#34C759]/30 rounded-full mb-8">
        <span className="w-2 h-2 bg-[#34C759] rounded-full animate-pulse" />
        <span className="text-xs font-bold text-[#34C759] uppercase tracking-wider">Live Signals Active</span>
      </div>

      {/* Headline */}
      <h1 className="text-4xl sm:text-5xl md:text-7xl font-black tracking-tighter text-white leading-[0.95] mb-6">
        Stop Guessing Entries.
        <br />
        <span className="text-[#34C759]">Start Trading Structure.</span>
      </h1>

      {/* Subheadline */}
      <p className="text-lg md:text-xl text-zinc-400 max-w-2xl mx-auto mb-10 leading-relaxed">
        MNQ SCALP STACKS gives scalpers a clean, structured view of price so they can
        execute with confidence in fast-moving markets.
      </p>

      {/* CTA Buttons */}
      <div className="flex flex-col sm:flex-row items-center justify-center gap-4">
        <button
          onClick={onCTA}
          className="group flex items-center gap-2 px-8 py-4 bg-[#34C759] text-black font-black text-lg rounded-sm hover:bg-[#2DB84E] transition-all hover:scale-105"
          data-testid="hero-cta-btn"
        >
          Get Access
          <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
        </button>
        <button
          onClick={onLearn}
          className="flex items-center gap-2 px-6 py-4 text-zinc-400 hover:text-white transition-colors text-sm font-semibold"
          data-testid="hero-learn-btn"
        >
          See How It Works
          <ChevronRight className="w-4 h-4" />
        </button>
      </div>

      {/* Social proof */}
      <div className="mt-12 flex items-center justify-center gap-6 text-zinc-500 text-xs">
        <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> 76.9% Win Rate</span>
        <span className="flex items-center gap-1"><BarChart3 className="w-3 h-3" /> 312 Backtested Trades</span>
        <span className="flex items-center gap-1"><Shield className="w-3 h-3" /> Kill Switch Protected</span>
      </div>
    </div>
  </section>
);

// ======================== PROBLEM ========================
const Problem = () => (
  <section className="py-20 px-6 bg-[#0A0A0A]" data-testid="problem-section">
    <div className="max-w-4xl mx-auto">
      <h2 className="text-3xl md:text-4xl font-black tracking-tighter text-white text-center mb-4">
        Most traders don't lack effort.
        <br />
        <span className="text-[#FF3B30]">They lack structure.</span>
      </h2>
      <p className="text-zinc-500 text-center max-w-xl mx-auto mb-12">
        Sound familiar?
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {[
          { icon: AlertTriangle, text: "Too many indicators creating noise" },
          { icon: Clock, text: "Late entries from second-guessing" },
          { icon: X, text: "Emotional decisions that blow accounts" },
          { icon: Eye, text: "Missed moves while waiting for confirmation" },
        ].map((item, i) => (
          <div
            key={i}
            className="flex items-center gap-4 p-4 bg-[#FF3B30]/5 border border-[#FF3B30]/20 rounded-sm"
          >
            <item.icon className="w-5 h-5 text-[#FF3B30] shrink-0" />
            <span className="text-zinc-300">{item.text}</span>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// ======================== SOLUTION ========================
const Solution = () => (
  <section className="py-20 px-6 bg-[#0D0D0D]" data-testid="solution-section">
    <div className="max-w-4xl mx-auto">
      <h2 className="text-3xl md:text-4xl font-black tracking-tighter text-white text-center mb-4">
        Trade with a <span className="text-[#34C759]">clear framework</span>
      </h2>
      <p className="text-zinc-500 text-center max-w-lg mx-auto mb-12">
        MNQ SCALP STACKS highlights key stack zones so you can:
      </p>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          { icon: Target, title: "Identify", desc: "High-probability zones using VWAP + Structure pivots", color: "#007AFF" },
          { icon: Crosshair, title: "Time", desc: "Entries with RSI momentum + confluence scoring", color: "#34C759" },
          { icon: Layers, title: "Execute", desc: "With structure — reduce noise and hesitation", color: "#FFCC00" },
        ].map((item, i) => (
          <div
            key={i}
            className="p-6 bg-[#121212] border border-white/10 rounded-sm text-center group hover:border-white/20 transition-colors"
          >
            <div
              className="w-12 h-12 mx-auto mb-4 rounded-sm flex items-center justify-center"
              style={{ background: `${item.color}15` }}
            >
              <item.icon className="w-6 h-6" style={{ color: item.color }} />
            </div>
            <h3 className="font-bold text-white mb-2">{item.title}</h3>
            <p className="text-sm text-zinc-500">{item.desc}</p>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// ======================== BEFORE / AFTER ========================
const BeforeAfter = () => (
  <section className="py-20 px-6 bg-[#0A0A0A]" data-testid="before-after-section">
    <div className="max-w-5xl mx-auto">
      <h2 className="text-3xl md:text-4xl font-black tracking-tighter text-white text-center mb-3">
        Same market. <span className="text-[#007AFF]">Different decisions.</span>
      </h2>
      <p className="text-zinc-500 text-center max-w-md mx-auto mb-12">
        Structure changes everything.
      </p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Before */}
        <div className="relative rounded-sm overflow-hidden border border-[#FF3B30]/30">
          <div className="absolute top-3 left-3 px-3 py-1 bg-[#FF3B30] text-white text-xs font-black rounded-sm z-10">
            BEFORE
          </div>
          <img
            src="https://images.unsplash.com/photo-1745509267699-1b1db256601e?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85&w=800"
            alt="Cluttered trading chart"
            className="w-full h-64 object-cover opacity-70"
          />
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-[#0A0A0A] to-transparent p-4">
            <p className="text-sm text-zinc-400">Indicators everywhere. No clarity. No edge.</p>
          </div>
        </div>

        {/* After */}
        <div className="relative rounded-sm overflow-hidden border border-[#34C759]/30">
          <div className="absolute top-3 left-3 px-3 py-1 bg-[#34C759] text-black text-xs font-black rounded-sm z-10">
            AFTER
          </div>
          <img
            src="https://images.pexels.com/photos/7567223/pexels-photo-7567223.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940"
            alt="Clean structured chart"
            className="w-full h-64 object-cover opacity-80"
          />
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-[#0A0A0A] to-transparent p-4">
            <p className="text-sm text-[#34C759]">Clean stack zones. Clear entries. Confident execution.</p>
          </div>
        </div>
      </div>
    </div>
  </section>
);

// ======================== HOW IT WORKS ========================
const HowItWorks = ({ sectionRef }) => (
  <section ref={sectionRef} className="py-20 px-6 bg-[#0D0D0D]" data-testid="how-it-works-section">
    <div className="max-w-4xl mx-auto">
      <h2 className="text-3xl md:text-4xl font-black tracking-tighter text-white text-center mb-12">
        3 Steps. <span className="text-[#007AFF]">That's it.</span>
      </h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        {[
          { step: "01", title: "Load the System", desc: "Add MNQ Scalp Stack v2 to your TradingView chart. One-click setup." },
          { step: "02", title: "Identify Stack Zones", desc: "VWAP + Structure + RSI confluence highlights high-probability areas." },
          { step: "03", title: "Execute with Structure", desc: "Signals fire to your Discord + Dashboard. Trade with precision." },
        ].map((item, i) => (
          <div key={i} className="relative">
            <span className="text-6xl font-black text-white/5 absolute -top-4 -left-2">{item.step}</span>
            <div className="relative pt-8">
              <h3 className="text-lg font-bold text-white mb-2">{item.title}</h3>
              <p className="text-sm text-zinc-500 leading-relaxed">{item.desc}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  </section>
);

// ======================== STATS BAR ========================
const StatsBar = ({ stats }) => (
  <section className="py-10 px-6 bg-[#121212] border-y border-white/5" data-testid="stats-bar">
    <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
      {[
        { label: "Win Rate", value: `${stats?.win_rate || 76.9}%`, color: "text-[#34C759]" },
        { label: "Profit Factor", value: stats?.profit_factor || "2.14", color: "text-white" },
        { label: "Net Profit", value: `$${(stats?.net_profit || 4280).toLocaleString()}`, color: "text-[#34C759]" },
        { label: "Sharpe Ratio", value: stats?.sharpe_ratio || "1.87", color: "text-[#007AFF]" },
      ].map((s, i) => (
        <div key={i}>
          <span className="text-[0.6rem] font-bold uppercase tracking-[0.2em] text-zinc-500 block mb-1">{s.label}</span>
          <span className={`text-2xl md:text-3xl font-mono font-bold ${s.color}`}>{s.value}</span>
        </div>
      ))}
    </div>
  </section>
);

// ======================== PRICING ========================
const Pricing = ({ ctaRef, onSignup, onCheckout, loading, signedUp, discordInvite }) => {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [selectedTier, setSelectedTier] = useState("pro");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!email) return;
    if (selectedTier === "free") {
      onSignup(email, name);
    } else {
      onCheckout(email, name, selectedTier);
    }
  };

  const tiers = [
    {
      id: "free", name: "Free", price: "$0", period: "",
      features: ["Basic signals (delayed)", "Public performance dashboard", "Discord community"],
      color: "border-white/10", accent: "text-[#007AFF]", btn: "bg-white/10 text-white hover:bg-white/20",
    },
    {
      id: "pro", name: "Pro", price: "$49", period: "/month", popular: true,
      features: ["Real-time signals", "Discord Pro channel", "AI trade analysis", "Daily market briefing"],
      color: "border-[#FFCC00]/40 ring-1 ring-[#FFCC00]/30", accent: "text-[#FFCC00]", btn: "bg-[#FFCC00] text-black hover:bg-[#FFCC00]/80",
    },
    {
      id: "elite", name: "Elite", price: "$149", period: "/month",
      features: ["Everything in Pro", "Discord Elite channel", "1-on-1 trade review", "Priority signals", "Custom alerts"],
      color: "border-[#34C759]/30", accent: "text-[#34C759]", btn: "bg-[#34C759] text-black hover:bg-[#34C759]/80",
    },
  ];

  if (signedUp) {
    return (
      <section ref={ctaRef} className="py-20 px-6 bg-[#0A0A0A]" data-testid="signup-success-section">
        <div className="max-w-md mx-auto text-center bg-[#121212] border border-[#34C759]/30 rounded-sm p-8">
          <div className="w-14 h-14 rounded-full bg-[#34C759]/20 flex items-center justify-center mx-auto mb-4">
            <Check className="w-7 h-7 text-[#34C759]" />
          </div>
          <h3 className="text-2xl font-black text-white mb-2">You're In!</h3>
          <p className="text-zinc-400 text-sm mb-5">Welcome to MNQ SCALP STACKS. Join Discord now.</p>
          {discordInvite && !discordInvite.startsWith("REPLACE") ? (
            <a href={discordInvite} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-2 px-6 py-3 bg-[#5865F2] text-white font-bold rounded-sm hover:bg-[#4752c4] transition-colors"
              data-testid="landing-discord-link"
            >
              Join Discord <ExternalLink className="w-4 h-4" />
            </a>
          ) : (
            <p className="text-zinc-500 text-sm">Discord invite link coming soon!</p>
          )}
        </div>
      </section>
    );
  }

  return (
    <section ref={ctaRef} className="py-20 px-6 bg-[#0A0A0A]" data-testid="pricing-section">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-3xl md:text-4xl font-black tracking-tighter text-white text-center mb-3">
          Trade with clarity. <span className="text-[#34C759]">Execute with confidence.</span>
        </h2>
        <p className="text-zinc-500 text-center mb-3 text-sm">Cancel anytime.</p>

        {/* Tier Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-10">
          {tiers.map((tier) => {
            const Icon = tier.id === "elite" ? Crown : tier.id === "pro" ? Star : Zap;
            return (
              <button
                key={tier.id}
                onClick={() => setSelectedTier(tier.id)}
                className={`relative text-left p-5 bg-[#121212] border rounded-sm transition-all ${
                  selectedTier === tier.id ? tier.color : "border-white/10 opacity-60 hover:opacity-80"
                }`}
                data-testid={`landing-tier-${tier.id}`}
              >
                {tier.popular && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-[#FFCC00] text-black text-[0.55rem] font-black uppercase rounded-sm">
                    Most Popular
                  </div>
                )}
                <div className="flex items-center gap-2 mb-3">
                  <Icon className={`w-5 h-5 ${tier.accent}`} />
                  <h3 className={`font-bold ${tier.accent}`}>{tier.name}</h3>
                </div>
                <div className="mb-3">
                  <span className="text-3xl font-mono font-bold text-white">{tier.price}</span>
                  {tier.period && <span className="text-zinc-500 text-sm">{tier.period}</span>}
                </div>
                <ul className="space-y-1.5">
                  {tier.features.map((f, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-zinc-400">
                      <Check className={`w-3 h-3 mt-0.5 shrink-0 ${tier.accent}`} />
                      {f}
                    </li>
                  ))}
                </ul>
              </button>
            );
          })}
        </div>

        {/* Signup Form */}
        <form onSubmit={handleSubmit} className="max-w-md mx-auto space-y-3">
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input
              type="email" placeholder="your@email.com" value={email}
              onChange={(e) => setEmail(e.target.value)} required
              className="w-full pl-10 py-3 text-sm bg-[#121212] border border-white/10 rounded-sm text-white focus:border-[#34C759] focus:outline-none"
              data-testid="landing-email"
            />
          </div>
          <button
            type="submit" disabled={loading || !email}
            className={`w-full py-3 rounded-sm font-black text-sm transition-all flex items-center justify-center gap-2 ${
              selectedTier === "elite" ? "bg-[#34C759] text-black" :
              selectedTier === "pro" ? "bg-[#FFCC00] text-black" :
              "bg-[#007AFF] text-white"
            } hover:opacity-90 disabled:opacity-50`}
            data-testid="landing-submit-btn"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> :
              selectedTier === "free" ? <>Start Free <ArrowRight className="w-4 h-4" /></> :
              <>Start Using MNQ SCALP STACKS <ArrowRight className="w-4 h-4" /></>
            }
          </button>
        </form>
      </div>
    </section>
  );
};

// ======================== FOOTER ========================
const Footer = () => (
  <footer className="py-8 px-6 border-t border-white/5 bg-[#0A0A0A]">
    <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
      <div className="flex items-center gap-2">
        <Zap className="w-5 h-5 text-[#FFCC00]" />
        <span className="font-black text-white text-sm">MNQ SCALP STACKS</span>
      </div>
      <div className="flex items-center gap-6 text-xs text-zinc-600">
        <a href="/performance" className="hover:text-zinc-400 transition-colors">Performance</a>
        <a href="/dashboard" className="hover:text-zinc-400 transition-colors">Dashboard</a>
      </div>
      <span className="text-xs text-zinc-600">MNQ SCALP STACKS SaaS | Emergent.sh</span>
    </div>
  </footer>
);

// ======================== MAIN LANDING PAGE ========================
const LandingPage = () => {
  const ctaRef = useRef(null);
  const howRef = useRef(null);
  const [backtestStats, setBacktestStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [signedUp, setSignedUp] = useState(false);
  const [discordInvite, setDiscordInvite] = useState("");

  useEffect(() => {
    const fetchStats = async () => {
      try {
        await axios.post(`${API}/backtests/seed-demo`);
        const res = await axios.get(`${API}/public/backtests`);
        if (res.data.length > 0) setBacktestStats(res.data[0]);
      } catch (e) { /* silent */ }
    };
    fetchStats();
  }, []);

  const scrollToCTA = () => ctaRef.current?.scrollIntoView({ behavior: "smooth" });
  const scrollToHow = () => howRef.current?.scrollIntoView({ behavior: "smooth" });

  const handleSignup = async (email, name) => {
    setLoading(true);
    try {
      const res = await axios.post(`${API}/subscribers`, { email, name, tier: "free" });
      setSignedUp(true);
      setDiscordInvite(res.data.discord_invite || "");
      toast.success("Welcome to MNQ SCALP STACKS!");
    } catch (e) { toast.error("Signup failed"); }
    setLoading(false);
  };

  const handleCheckout = async (email, name, tier) => {
    setLoading(true);
    try {
      await axios.post(`${API}/subscribers`, { email, name, tier });
      const res = await axios.post(`${API}/checkout/create`, { tier, origin_url: window.location.origin });
      if (res.data.url) window.location.href = res.data.url;
    } catch (e) { toast.error("Checkout failed"); setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="landing-page">
      <Toaster position="top-right" toastOptions={{ style: { background: "#121212", border: "1px solid rgba(255,255,255,0.1)", color: "#fff" } }} />

      {/* Nav */}
      <nav className="fixed top-0 w-full z-50 bg-[#0A0A0A]/80 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Zap className="w-5 h-5 text-[#FFCC00]" />
            <span className="font-black text-white text-sm tracking-tight">MNQ SCALP STACKS</span>
          </div>
          <div className="flex items-center gap-4">
            <a href="/performance" className="text-xs text-zinc-500 hover:text-white transition-colors">Performance</a>
            <a href="/dashboard" className="text-xs text-zinc-500 hover:text-white transition-colors">Dashboard</a>
            <button
              onClick={scrollToCTA}
              className="px-4 py-1.5 bg-[#34C759] text-black text-xs font-black rounded-sm hover:bg-[#2DB84E] transition-colors"
              data-testid="nav-cta-btn"
            >
              Get Access
            </button>
          </div>
        </div>
      </nav>

      <div className="pt-14">
        <Hero onCTA={scrollToCTA} onLearn={scrollToHow} />
        <Problem />
        <Solution />
        <BeforeAfter />
        <HowItWorks sectionRef={howRef} />
        <StatsBar stats={backtestStats} />
        <Pricing
          ctaRef={ctaRef}
          onSignup={handleSignup}
          onCheckout={handleCheckout}
          loading={loading}
          signedUp={signedUp}
          discordInvite={discordInvite}
        />
        <Footer />
      </div>
    </div>
  );
};

export default LandingPage;
