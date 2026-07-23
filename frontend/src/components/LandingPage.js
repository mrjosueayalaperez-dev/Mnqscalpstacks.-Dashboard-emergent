import React, { useState, useEffect, useRef, useCallback } from "react";
import axios from "axios";
import { Toaster, toast } from "sonner";
import ProofGallery from "./ProofGallery";
import {
  Zap, TrendingUp, Target, Shield, ChevronRight, Check, X, Star, Crown,
  BarChart3, Clock, Activity, ArrowRight, Eye, Crosshair, Layers, Mail,
  User, Loader2, ExternalLink, AlertTriangle, Copy, Gift, Share2, Users,
  ChevronDown, Flame,
} from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// ======================== SCROLL REVEAL HOOK ========================
const useReveal = () => {
  const ref = useRef(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { el.classList.add("visible"); observer.unobserve(el); } },
      { threshold: 0.15 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, []);
  return ref;
};

// ======================== ANIMATED COUNTER ========================
const AnimatedCounter = ({ end, duration = 2000, prefix = "", suffix = "" }) => {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          const startTime = Date.now();
          const animate = () => {
            const elapsed = Date.now() - startTime;
            const progress = Math.min(elapsed / duration, 1);
            const eased = 1 - Math.pow(1 - progress, 3);
            setCount(Math.floor(eased * end));
            if (progress < 1) requestAnimationFrame(animate);
          };
          animate();
        }
      },
      { threshold: 0.5 }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [end, duration]);

  return <span ref={ref}>{prefix}{count}{suffix}</span>;
};

// ======================== SOCIAL PROOF TICKER ========================
const SocialProofTicker = () => {
  const [count, setCount] = useState(0);

  useEffect(() => {
    axios.get(`${API}/subscribers/count`).then(r => setCount(r.data.total || 0)).catch(() => setCount(15));
  }, []);

  if (count === 0) return null;

  return (
    <div className="fixed bottom-4 left-4 z-40 animate-fade-in stagger-6 hidden md:flex items-center gap-2 px-4 py-2 bg-[#121212] border border-[#34C759]/30 rounded-sm shadow-lg" data-testid="social-proof-ticker">
      <div className="w-2 h-2 bg-[#34C759] rounded-full animate-pulse" />
      <span className="text-xs text-zinc-300">
        <strong className="text-[#34C759]">{count}+ traders</strong> joined this week
      </span>
      <Flame className="w-3 h-3 text-[#FFCC00]" />
    </div>
  );
};

// ======================== HERO ========================
const Hero = ({ onCTA, onLearn }) => (
  <section className="relative min-h-[85vh] md:min-h-[90vh] flex items-center overflow-hidden" data-testid="hero-section">
    <div className="absolute inset-0 bg-[#0A0A0A]">
      <div className="absolute inset-0 opacity-15 md:opacity-20"
        style={{ backgroundImage: `url(https://images.unsplash.com/photo-1745270917233-65e776a47547?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85&w=1920)`, backgroundSize: "cover", backgroundPosition: "center" }}
      />
      <div className="absolute inset-0 bg-gradient-to-b from-[#0A0A0A]/60 via-[#0A0A0A]/80 to-[#0A0A0A]" />
    </div>
    <div className="relative w-full max-w-5xl mx-auto px-5 md:px-6 py-16 md:py-20 text-center">
      <div className="inline-flex items-center gap-2 px-3 py-1 bg-[#34C759]/10 border border-[#34C759]/30 rounded-full mb-6 md:mb-8 animate-fade-in-up">
        <span className="w-2 h-2 bg-[#34C759] rounded-full animate-pulse" />
        <span className="text-[0.65rem] md:text-xs font-bold text-[#34C759] uppercase tracking-wider">Live Signals Active</span>
      </div>
      <h1 className="text-3xl sm:text-4xl md:text-6xl lg:text-7xl font-black tracking-tighter text-white leading-[0.95] mb-5 md:mb-6 animate-fade-in-up stagger-1">
        Stop Guessing Entries.
        <br />
        <span className="text-[#34C759]">Start Trading Structure.</span>
      </h1>
      <p className="text-base md:text-xl text-zinc-400 max-w-2xl mx-auto mb-8 md:mb-10 leading-relaxed px-2 animate-fade-in-up stagger-2">
        Precision Futures Intelligence. Take the guesswork out of the 1-minute chart with proprietary Wave Validation and institutional guardrails.
      </p>
      <div className="flex flex-col sm:flex-row items-center justify-center gap-3 md:gap-4 animate-fade-in-up stagger-3">
        <button onClick={onCTA} className="group w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-4 bg-[#34C759] text-black font-black text-base md:text-lg rounded-sm hover:bg-[#2DB84E] transition-all active:scale-95 animate-pulse-glow" data-testid="hero-cta-btn">
          Get Access <ArrowRight className="w-5 h-5 group-hover:translate-x-1 transition-transform" />
        </button>
        <button onClick={onLearn} className="flex items-center gap-2 px-6 py-3 text-zinc-400 hover:text-white transition-colors text-sm font-semibold" data-testid="hero-learn-btn">
          See How It Works <ChevronDown className="w-4 h-4" />
        </button>
      </div>
      <div className="mt-10 md:mt-12 flex flex-wrap items-center justify-center gap-4 md:gap-6 text-zinc-500 text-[0.65rem] md:text-xs animate-fade-in-up stagger-4">
        <span className="flex items-center gap-1"><Activity className="w-3 h-3" /> <AnimatedCounter end={77} suffix=".3% Win Rate" /></span>
        <span className="flex items-center gap-1"><BarChart3 className="w-3 h-3" /> Competition Tested</span>
        <span className="flex items-center gap-1"><Shield className="w-3 h-3" /> Wave Validated</span>
      </div>
    </div>
  </section>
);

// ======================== PROBLEM ========================
const Problem = () => {
  const ref = useReveal();
  return (
  <section ref={ref} className="py-14 md:py-20 px-5 md:px-6 bg-[#0A0A0A] reveal" data-testid="problem-section">
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl md:text-4xl font-black tracking-tighter text-white text-center mb-3 md:mb-4">
        Most traders don't lack effort. <span className="text-[#FF3B30]">They lack structure.</span>
      </h2>
      <p className="text-zinc-500 text-center text-sm mb-8 md:mb-12">Sound familiar?</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 md:gap-4">
        {[
          { icon: AlertTriangle, text: "Too many indicators creating noise" },
          { icon: Clock, text: "Late entries from second-guessing" },
          { icon: X, text: "Emotional decisions that blow accounts" },
          { icon: Eye, text: "Missed moves while waiting for confirmation" },
        ].map((item) => (
          <div key={item.text} className="flex items-center gap-3 md:gap-4 p-3 md:p-4 bg-[#FF3B30]/5 border border-[#FF3B30]/20 rounded-sm">
            <item.icon className="w-5 h-5 text-[#FF3B30] shrink-0" />
            <span className="text-sm text-zinc-300">{item.text}</span>
          </div>
        ))}
      </div>
    </div>
  </section>
  );
};

// ======================== SOLUTION ========================
const Solution = () => {
  const ref = useReveal();
  return (
  <section ref={ref} className="py-14 md:py-20 px-5 md:px-6 bg-[#0D0D0D] reveal" data-testid="solution-section">
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl md:text-4xl font-black tracking-tighter text-white text-center mb-3">
        Trade with a <span className="text-[#34C759]">clear framework</span>
      </h2>
      <p className="text-zinc-500 text-center text-sm max-w-lg mx-auto mb-8 md:mb-12">MNQ Scalp Stacks delivers precision futures intelligence:</p>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 md:gap-6">
        {[
          { icon: Target, title: "Wave Validation", desc: "High-probability entries backed by a 77.3% historical win rate", color: "#007AFF" },
          { icon: Crosshair, title: "Institutional Guardrails", desc: "Automated detection of psychological levels and resistance zones", color: "#34C759" },
          { icon: Layers, title: "Full Stack Integration", desc: "Pine Script v3 synced with Python backend for zero-lag execution", color: "#FFCC00" },
        ].map((item) => (
          <div key={item.title} className="p-5 md:p-6 bg-[#121212] border border-white/10 rounded-sm text-center hover:border-white/20 transition-colors">
            <div className="w-12 h-12 mx-auto mb-4 rounded-sm flex items-center justify-center" style={{ background: `${item.color}15` }}>
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
};

// ======================== BEFORE / AFTER ========================
const BeforeAfter = () => {
  const ref = useReveal();
  return (
  <section ref={ref} className="py-14 md:py-20 px-5 md:px-6 bg-[#0A0A0A] reveal" data-testid="before-after-section">
    <div className="max-w-5xl mx-auto">
      <h2 className="text-2xl md:text-4xl font-black tracking-tighter text-white text-center mb-2">
        Same market. <span className="text-[#007AFF]">Different decisions.</span>
      </h2>
      <p className="text-zinc-500 text-center text-sm mb-8 md:mb-12">Structure changes everything.</p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 md:gap-6">
        <div className="relative rounded-sm overflow-hidden border border-[#FF3B30]/30">
          <div className="absolute top-3 left-3 px-3 py-1 bg-[#FF3B30] text-white text-xs font-black rounded-sm z-10">BEFORE</div>
          <img src="https://images.unsplash.com/photo-1745509267699-1b1db256601e?crop=entropy&cs=srgb&fm=jpg&ixlib=rb-4.1.0&q=85&w=800" alt="Cluttered chart" className="w-full h-48 md:h-64 object-cover opacity-70" />
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-[#0A0A0A] to-transparent p-4">
            <p className="text-sm text-zinc-400">Indicators everywhere. No clarity. No edge.</p>
          </div>
        </div>
        <div className="relative rounded-sm overflow-hidden border border-[#34C759]/30">
          <div className="absolute top-3 left-3 px-3 py-1 bg-[#34C759] text-black text-xs font-black rounded-sm z-10">AFTER</div>
          <img src="https://images.pexels.com/photos/7567223/pexels-photo-7567223.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940" alt="Clean chart" className="w-full h-48 md:h-64 object-cover opacity-80" />
          <div className="absolute bottom-0 inset-x-0 bg-gradient-to-t from-[#0A0A0A] to-transparent p-4">
            <p className="text-sm text-[#34C759]">Clean stack zones. Clear entries. Confident execution.</p>
          </div>
        </div>
      </div>
    </div>
  </section>
  );
};

// ======================== HOW IT WORKS ========================
const HowItWorks = ({ sectionRef }) => (
  <section ref={sectionRef} className="py-14 md:py-20 px-5 md:px-6 bg-[#0D0D0D] reveal visible" data-testid="how-it-works-section">
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl md:text-4xl font-black tracking-tighter text-white text-center mb-8 md:mb-12">
        3 Steps. <span className="text-[#007AFF]">That's it.</span>
      </h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 md:gap-8">
        {[
          { step: "01", title: "Load the System", desc: "Add MNQ Scalp Stacks v3 to your TradingView 1-min chart. One click." },
          { step: "02", title: "Wave Validation", desc: "EMA 21 Spine + VWAP + 27,972 resistance — the system does the thinking." },
          { step: "03", title: "Execute the Punch", desc: "BUY/SELL Punches fire to Discord + Dashboard. Trade with precision." },
        ].map((item) => (
          <div key={item.step} className="relative">
            <span className="text-5xl md:text-6xl font-black text-white/5 absolute -top-2 md:-top-4 -left-1 md:-left-2">{item.step}</span>
            <div className="relative pt-6 md:pt-8">
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
  <section className="py-8 md:py-10 px-5 md:px-6 bg-[#121212] border-y border-white/5" data-testid="stats-bar">
    <div className="max-w-5xl mx-auto grid grid-cols-2 md:grid-cols-4 gap-4 md:gap-6 text-center">
      {[
        { label: "Win Rate", value: `${stats?.win_rate || 76.9}%`, color: "text-[#34C759]" },
        { label: "Profit Factor", value: stats?.profit_factor || "2.14", color: "text-white" },
        { label: "Net Profit", value: `$${(stats?.net_profit || 4280).toLocaleString()}`, color: "text-[#34C759]" },
        { label: "Sharpe Ratio", value: stats?.sharpe_ratio || "1.87", color: "text-[#007AFF]" },
      ].map((s) => (
        <div key={s.label}>
          <span className="text-[0.55rem] md:text-[0.6rem] font-bold uppercase tracking-[0.2em] text-zinc-500 block mb-1">{s.label}</span>
          <span className={`text-xl md:text-3xl font-mono font-bold ${s.color}`}>{s.value}</span>
        </div>
      ))}
    </div>
  </section>
);

// ======================== REFERRAL BANNER ========================
const ReferralBanner = ({ referralCode, onCopy }) => {
  const [copied, setCopied] = useState(false);
  const link = `${window.location.origin}?ref=${referralCode}`;

  const handleCopy = () => {
    navigator.clipboard.writeText(link);
    setCopied(true);
    onCopy?.();
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-[#121212] border border-[#FFCC00]/30 rounded-sm p-4 md:p-5 text-center" data-testid="referral-banner">
      <div className="flex items-center justify-center gap-2 mb-2">
        <Gift className="w-5 h-5 text-[#FFCC00]" />
        <h3 className="font-bold text-white text-sm md:text-base">Share & Earn Free Months</h3>
      </div>
      <p className="text-zinc-500 text-xs mb-3">Each friend you refer = 1 month free credit for you!</p>
      <div className="flex items-center gap-2 max-w-md mx-auto">
        <div className="flex-1 bg-white/5 border border-white/10 rounded-sm px-3 py-2 text-xs font-mono text-zinc-300 truncate">
          {link}
        </div>
        <button onClick={handleCopy} className="px-3 py-2 bg-[#FFCC00] text-black font-bold text-xs rounded-sm hover:bg-[#FFCC00]/80 transition-colors flex items-center gap-1 shrink-0" data-testid="copy-referral-btn">
          {copied ? <Check className="w-3 h-3" /> : <Copy className="w-3 h-3" />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
    </div>
  );
};

// ======================== WELCOME ONBOARDING ========================
const WelcomeOnboarding = ({ steps, onComplete }) => {
  if (!steps || steps.length === 0) return null;
  const completedCount = steps.filter(s => s.completed).length;
  const progress = (completedCount / steps.length) * 100;
  const stepIcons = { welcome: Zap, action: ExternalLink, setup: BarChart3, education: Target, referral: Gift };

  return (
    <div className="bg-[#121212] border border-[#007AFF]/30 rounded-sm p-4 md:p-5" data-testid="welcome-onboarding">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-bold text-white text-sm flex items-center gap-2">
          <Zap className="w-4 h-4 text-[#007AFF]" /> Getting Started
        </h3>
        <span className="text-xs font-mono text-zinc-500">{completedCount}/{steps.length}</span>
      </div>
      <div className="h-1 bg-white/10 rounded-full overflow-hidden mb-4">
        <div className="h-full bg-[#007AFF] transition-all duration-500" style={{ width: `${progress}%` }} />
      </div>
      <div className="space-y-2">
        {steps.map((step) => {
          const Icon = stepIcons[step.type] || Check;
          return (
            <div key={step.id} className={`flex items-start gap-3 p-2 rounded-sm transition-colors ${step.completed ? "opacity-50" : "hover:bg-white/5"}`} data-testid={`welcome-step-${step.step}`}>
              <button
                onClick={() => !step.completed && onComplete(step.id)}
                className={`w-5 h-5 rounded-sm border flex items-center justify-center shrink-0 mt-0.5 transition-colors ${
                  step.completed ? "bg-[#34C759] border-[#34C759]" : "border-zinc-600 hover:border-[#007AFF]"
                }`}
              >
                {step.completed && <Check className="w-3 h-3 text-white" />}
              </button>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <Icon className="w-3 h-3 text-zinc-500" />
                  <span className={`text-sm font-semibold ${step.completed ? "line-through text-zinc-500" : "text-white"}`}>{step.title}</span>
                </div>
                <p className="text-xs text-zinc-500 mt-0.5">{step.message}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

// ======================== PRICING + SIGNUP ========================
const Pricing = ({ ctaRef, onSignup, onCheckout, loading, signedUp, discordInvite, referralCode, welcomeSteps, onCompleteStep, referrerName }) => {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [selectedTier, setSelectedTier] = useState("pro");

  const tiers = [
    { id: "free", name: "Free", price: "$0", period: "", features: ["Basic signals (delayed)", "Public dashboard", "Discord community"], color: "border-white/10", accent: "text-[#007AFF]" },
    { id: "pro", name: "Pro", price: "$49", period: "/mo", popular: true, features: ["Real-time signals", "Discord Pro channel", "AI trade analysis", "Daily briefing"], color: "border-[#FFCC00]/40 ring-1 ring-[#FFCC00]/30", accent: "text-[#FFCC00]" },
    { id: "elite", name: "Elite", price: "$149", period: "/mo", features: ["Everything in Pro", "Elite Discord", "1-on-1 review", "Priority signals", "Custom alerts"], color: "border-[#34C759]/30", accent: "text-[#34C759]" },
  ];

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!email) return;
    selectedTier === "free" ? onSignup(email, name) : onCheckout(email, name, selectedTier);
  };

  // Post-signup view
  if (signedUp) {
    return (
      <section ref={ctaRef} className="py-14 md:py-20 px-5 md:px-6 bg-[#0A0A0A]" data-testid="post-signup-section">
        <div className="max-w-lg mx-auto space-y-4">
          {/* Success card */}
          <div className="text-center bg-[#121212] border border-[#34C759]/30 rounded-sm p-6">
            <div className="w-14 h-14 rounded-full bg-[#34C759]/20 flex items-center justify-center mx-auto mb-4">
              <Check className="w-7 h-7 text-[#34C759]" />
            </div>
            <h3 className="text-xl md:text-2xl font-black text-white mb-2">You're In!</h3>
            <p className="text-zinc-400 text-sm mb-4">Welcome to MNQ SCALP STACKS.</p>
            {discordInvite && !discordInvite.startsWith("REPLACE") ? (
              <a href={discordInvite} target="_blank" rel="noopener noreferrer"
                className="inline-flex items-center gap-2 px-6 py-2.5 bg-[#5865F2] text-white font-bold rounded-sm hover:bg-[#4752c4] transition-colors text-sm" data-testid="landing-discord-link">
                Join Discord <ExternalLink className="w-4 h-4" />
              </a>
            ) : (
              <p className="text-zinc-500 text-sm">Discord invite coming soon!</p>
            )}
          </div>
          {/* Welcome onboarding */}
          <WelcomeOnboarding steps={welcomeSteps} onComplete={onCompleteStep} />
          {/* Referral */}
          {referralCode && <ReferralBanner referralCode={referralCode} onCopy={() => toast.success("Referral link copied!")} />}
        </div>
      </section>
    );
  }

  return (
    <section ref={ctaRef} className="py-14 md:py-20 px-5 md:px-6 bg-[#0A0A0A]" data-testid="pricing-section">
      <div className="max-w-5xl mx-auto">
        <h2 className="text-2xl md:text-4xl font-black tracking-tighter text-white text-center mb-2">
          Trade with clarity. <span className="text-[#34C759]">Execute with confidence.</span>
        </h2>
        <p className="text-zinc-500 text-center mb-2 text-sm">Cancel anytime.</p>
        {referrerName && (
          <p className="text-center text-xs text-[#FFCC00] mb-4">
            <Gift className="w-3 h-3 inline mr-1" /> Referred by {referrerName}
          </p>
        )}

        {/* Tier Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3 md:gap-4 mb-8 md:mb-10">
          {tiers.map((tier) => {
            const Icon = tier.id === "elite" ? Crown : tier.id === "pro" ? Star : Zap;
            return (
              <button key={tier.id} onClick={() => setSelectedTier(tier.id)}
                className={`relative text-left p-4 md:p-5 bg-[#121212] border rounded-sm transition-all ${selectedTier === tier.id ? tier.color : "border-white/10 opacity-60 hover:opacity-80"}`}
                data-testid={`landing-tier-${tier.id}`}>
                {tier.popular && <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-0.5 bg-[#FFCC00] text-black text-[0.55rem] font-black uppercase rounded-sm">Most Popular</div>}
                <div className="flex items-center gap-2 mb-2"><Icon className={`w-4 h-4 ${tier.accent}`} /><h3 className={`font-bold text-sm ${tier.accent}`}>{tier.name}</h3></div>
                <div className="mb-3"><span className="text-2xl md:text-3xl font-mono font-bold text-white">{tier.price}</span>{tier.period && <span className="text-zinc-500 text-sm">{tier.period}</span>}</div>
                <ul className="space-y-1">
                  {tier.features.map((f) => (<li key={f} className="flex items-start gap-2 text-xs text-zinc-400"><Check className={`w-3 h-3 mt-0.5 shrink-0 ${tier.accent}`} />{f}</li>))}
                </ul>
              </button>
            );
          })}
        </div>

        {/* Signup */}
        <form onSubmit={handleSubmit} className="max-w-md mx-auto space-y-3">
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
            <input type="email" placeholder="your@email.com" value={email} onChange={(e) => setEmail(e.target.value)} required
              className="w-full pl-10 py-3 text-sm bg-[#121212] border border-white/10 rounded-sm text-white focus:border-[#34C759] focus:outline-none" data-testid="landing-email" />
          </div>
          <button type="submit" disabled={loading || !email}
            className={`w-full py-3 rounded-sm font-black text-sm transition-all flex items-center justify-center gap-2 active:scale-[0.98] ${
              selectedTier === "elite" ? "bg-[#34C759] text-black" : selectedTier === "pro" ? "bg-[#FFCC00] text-black" : "bg-[#007AFF] text-white"
            } hover:opacity-90 disabled:opacity-50`} data-testid="landing-submit-btn">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> :
              selectedTier === "free" ? <>Start Free <ArrowRight className="w-4 h-4" /></> :
              <>Start Using MNQ SCALP STACKS <ArrowRight className="w-4 h-4" /></>}
          </button>
        </form>
      </div>
    </section>
  );
};

// ======================== FOOTER ========================
const Footer = () => (
  <footer className="py-6 md:py-8 px-5 md:px-6 border-t border-white/5 bg-[#0A0A0A]">
    <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-3 md:gap-4">
      <div className="flex items-center gap-2"><Zap className="w-5 h-5 text-[#FFCC00]" /><span className="font-black text-white text-sm">MNQ SCALP STACKS</span></div>
      <div className="flex items-center gap-6 text-xs text-zinc-600">
        <a href="/performance" className="hover:text-zinc-400 transition-colors">Performance</a>
        <a href="/dashboard" className="hover:text-zinc-400 transition-colors">Dashboard</a>
      </div>
      <span className="text-[0.65rem] text-zinc-600">MNQ SCALP STACKS SaaS | Emergent.sh</span>
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
  const [referralCode, setReferralCode] = useState("");
  const [welcomeSteps, setWelcomeSteps] = useState([]);
  const [subscriberId, setSubscriberId] = useState("");
  const [referrerName, setReferrerName] = useState("");

  // Check for referral code in URL
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get("ref");
    if (ref) {
      axios.get(`${API}/referral/${ref}`).then(r => {
        if (r.data.valid) setReferrerName(r.data.referrer_name);
      }).catch((e) => console.error("Referral lookup error:", e));
    }
  }, []);

  useEffect(() => {
    axios.post(`${API}/backtests/seed-demo`).catch((e) => console.error("Seed error:", e));
    axios.get(`${API}/public/backtests`).then(r => { if (r.data.length > 0) setBacktestStats(r.data[0]); }).catch((e) => console.error("Backtest fetch error:", e));
  }, []);

  // Check for payment return
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const sessionId = params.get("session_id");
    if (sessionId) {
      const poll = async (attempts = 0) => {
        if (attempts >= 5) return;
        try {
          const res = await axios.get(`${API}/checkout/status/${sessionId}`);
          if (res.data.payment_status === "paid") { setSignedUp(true); toast.success("Payment successful!"); }
          else if (res.data.status !== "expired") setTimeout(() => poll(attempts + 1), 2000);
        } catch (e) { console.error("Payment poll error:", e); }
      };
      poll();
      window.history.replaceState({}, "", "/");
    }
  }, []);

  const scrollToCTA = () => ctaRef.current?.scrollIntoView({ behavior: "smooth" });
  const scrollToHow = () => howRef.current?.scrollIntoView({ behavior: "smooth" });

  const handleSignup = async (email, name) => {
    setLoading(true);
    const params = new URLSearchParams(window.location.search);
    const refCode = params.get("ref") || null;
    try {
      const res = await axios.post(`${API}/subscribers`, { email, name, tier: "free", referral_code: refCode });
      setSignedUp(true);
      setDiscordInvite(res.data.discord_invite || "");
      setReferralCode(res.data.referral_code || res.data.subscriber?.referral_code || "");
      const subId = res.data.subscriber?.id;
      setSubscriberId(subId);
      if (subId) {
        const ws = await axios.get(`${API}/welcome/${subId}`);
        setWelcomeSteps(ws.data);
      }
      toast.success("Welcome to MNQ SCALP STACKS!");
    } catch (e) { toast.error("Signup failed"); }
    setLoading(false);
  };

  const handleCheckout = async (email, name, tier) => {
    setLoading(true);
    const params = new URLSearchParams(window.location.search);
    const refCode = params.get("ref") || null;
    try {
      // Create or get subscriber (idempotent)
      await axios.post(`${API}/subscribers`, { email, name, tier, referral_code: refCode });
      // Always create checkout for paid tiers
      const res = await axios.post(`${API}/checkout/create`, { tier, origin_url: window.location.origin });
      if (res.data.url) {
        window.location.href = res.data.url;
      } else {
        toast.error("No checkout URL returned");
        setLoading(false);
      }
    } catch (e) {
      console.error("Checkout error:", e);
      toast.error("Checkout failed: " + (e.response?.data?.detail || e.message || "Unknown error"));
      setLoading(false);
    }
  };

  const handleCompleteStep = async (stepId) => {
    try {
      await axios.patch(`${API}/welcome/${stepId}/complete`);
      setWelcomeSteps(prev => prev.map(s => s.id === stepId ? { ...s, completed: true } : s));
    } catch (e) { console.error("Welcome step error:", e); }
  };

  return (
    <div className="min-h-screen bg-[#0A0A0A]" data-testid="landing-page">
      <Toaster position="top-right" toastOptions={{ style: { background: "#121212", border: "1px solid rgba(255,255,255,0.1)", color: "#fff" } }} />
      <nav className="fixed top-0 w-full z-50 bg-[#0A0A0A]/80 backdrop-blur-xl border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 md:px-6 h-12 md:h-14 flex items-center justify-between">
          <div className="flex items-center gap-2"><Zap className="w-4 md:w-5 h-4 md:h-5 text-[#FFCC00]" /><span className="font-black text-white text-xs md:text-sm tracking-tight">MNQ SCALP STACKS</span></div>
          <div className="flex items-center gap-2 md:gap-4">
            <a href="/performance" className="hidden sm:inline text-xs text-zinc-500 hover:text-white transition-colors">Performance</a>
            <a href="/dashboard" className="hidden sm:inline text-xs text-zinc-500 hover:text-white transition-colors">Dashboard</a>
            <button onClick={scrollToCTA} className="px-3 md:px-4 py-1.5 bg-[#34C759] text-black text-xs font-black rounded-sm hover:bg-[#2DB84E] transition-colors" data-testid="nav-cta-btn">
              Get Access
            </button>
          </div>
        </div>
      </nav>
      <div className="pt-12 md:pt-14">
        <Hero onCTA={scrollToCTA} onLearn={scrollToHow} />
        <Problem />
        <Solution />
        <BeforeAfter />
        <HowItWorks sectionRef={howRef} />
        <StatsBar stats={backtestStats} />
        <ProofGallery />
        <Pricing ctaRef={ctaRef} onSignup={handleSignup} onCheckout={handleCheckout} loading={loading}
          signedUp={signedUp} discordInvite={discordInvite} referralCode={referralCode}
          welcomeSteps={welcomeSteps} onCompleteStep={handleCompleteStep} referrerName={referrerName} />
        <Footer />
        <SocialProofTicker />
      </div>
    </div>
  );
};

export default LandingPage;
