import React, { useState } from "react";
import { BookOpen, ChevronDown, ChevronRight, Zap, Shield, TrendingUp, Trophy, AlertTriangle, Target } from "lucide-react";

const educationTabs = {
  beginner: [
    {
      id: "fear",
      icon: AlertTriangle,
      title: "Why Most People Fail",
      color: "#FF3B30",
      content: `Most people fail at trading because they trade with EMOTIONS — fear and greed. They enter late because of FOMO. They hold losers because of HOPE. They revenge trade because of ANGER.

This dashboard removes the hard part. We use MATH (the EMAs) and MECHANICS (the $100 Shield) to make every decision for you.

If you follow the 21 EMA and the 200 EMA "Stack," the market becomes a series of green and red lights — not a guessing game.

Green light = Price above 21 EMA + VWAP = GO.
Red light = Anything else = WAIT.

That's it. No emotions. No guessing. Just structure.`
    },
    {
      id: "roof",
      icon: TrendingUp,
      title: "Following the Roof (200 EMA)",
      color: "#FFCC00",
      content: `The 200 EMA is the "Roof" of the market. When price is below it, the macro trend is bearish — you are under the roof.

As a beginner, your ONLY job is to RESPECT the roof. Never fight it. If price is under the 200 EMA, your bias is SHORT or FLAT. Period.

The 200 EMA moves slowly — it's your compass, not your steering wheel. Check it before every session.`
    },
    {
      id: "water",
      icon: Zap,
      title: "Navigating the Water (21 EMA)",
      color: "#007AFF",
      content: `The 21 EMA is the "Water" — the current you swim in. This is your SPINE on the 1-minute chart.

BUY PUNCH: Price crosses ABOVE the 21 EMA while ABOVE VWAP. The water is warm.
SELL PUNCH: Price crosses BELOW the 21 EMA while BELOW VWAP. The water is cold.

When the 21 EMA is FLAT, the water is still. DO NOT SWIM. Wait for the current.`
    },
    {
      id: "love",
      icon: Shield,
      title: "The $100 Love (Capital Protection)",
      color: "#34C759",
      content: `The $100 Love rule is NON-NEGOTIABLE. It is the ATM of discipline.

You walk into the session with $100 max risk. When the Safety Sentinel hits -$100, the system LOCKS. No overrides. No revenge trades.

Why $100? Because it's recoverable. A -$100 day is a lesson. A -$500 day is a wound. A -$2000 day is a funeral.

The math: At $0.50/tick on MNQ with a 40-tick stop, that's $20 per trade. You get 5 clean shots. Make them count.

This rule separates the disciplined from the gamblers. Love your capital. It loves you back.`
    },
  ],
  advanced: [
    {
      id: "vwap",
      icon: Target,
      title: "The Institutional Level (VWAP)",
      color: "#007AFF",
      content: `VWAP is where the institutions play. It represents the average price weighted by volume — the "fair value" of the session.

Above VWAP: Buyers in control. Hydro-Pilot shows GO.
Below VWAP: Sellers in control. Hydro-Pilot shows NO-GO for longs.

VWAP resets every session. The best Scalp Punch setups happen when price crosses the 21 EMA AND is on the right side of VWAP. That's confluence. That's the Punch.

Pro tip: VWAP is strongest 9:30-11:30 ET. After lunch, it gets choppy. Know when to trade and when to WAIT.`
    },
    {
      id: "scaling",
      icon: TrendingUp,
      title: "Precision Scaling",
      color: "#FFCC00",
      content: `Once you've proven consistency with 1 contract, scaling follows a strict protocol:

Stage 1: 1 contract, $100 daily limit. Prove 60%+ win rate over 20 sessions.
Stage 2: 2 contracts, $200 daily limit. Maintain 55%+ win rate.
Stage 3: 3+ contracts, $300+ daily limit. Only after 50+ profitable sessions.

NEVER skip stages. The $100 Shield scales WITH you. Double the contracts = double the shield.

The Pro Toggle exists for Stage 3+ traders ONLY. If you're using it in Stage 1, you're lying to yourself.`
    },
    {
      id: "stack",
      icon: Zap,
      title: "The EMA Stack Alignment",
      color: "#34C759",
      content: `The most powerful setup in MNQ is the FULL STACK ALIGNMENT:

Price > 21 EMA > 200 EMA > VWAP = Maximum bullish confluence.
Price < 21 EMA < 200 EMA < VWAP = Maximum bearish confluence.

When ALL THREE align, you have institutional + retail + structural support in one direction. These are the trades that run 80-100+ ticks.

When the stack is MIXED (price above 21 but below 200), you're in no-man's land. Reduce size or stand flat. The Hydro-Pilot shows WAIT for a reason.`
    },
  ],
};

const caseStudies = [
  {
    id: "case1",
    title: "Day 1: Stack Alignment Mastery",
    amount: "+$366.00",
    description: "Full EMA stack aligned bullish at open. 21 EMA held as support on every pullback. Three clean BUY Punches, all hitting TP within 15 minutes.",
    color: "#34C759",
  },
  {
    id: "case2",
    title: "Day 2: Pullback Support on 21 EMA",
    amount: "+$310.00",
    description: "Price pulled back to the Blue Spine (21 EMA) and bounced perfectly. The Hydro-Pilot showed GO at the exact moment of the bounce. Two trades, both winners.",
    color: "#007AFF",
  },
  {
    id: "case3",
    title: "Elite Trend Ride",
    amount: "+$1,215.00",
    description: "Major contract extension held below the 21 EMA Spine for 90 minutes. Structural short ride from 27,980 to 27,850. The $100 Shield was never triggered. Pure math.",
    color: "#FFCC00",
  },
];

const KnowledgeVault = () => {
  const [expanded, setExpanded] = useState(null);
  const [tab, setTab] = useState("beginner");

  const topics = educationTabs[tab];

  return (
    <div className="widget-panel col-span-1 md:col-span-4 lg:col-span-4" data-testid="knowledge-vault">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-[#007AFF]" />
          KNOWLEDGE VAULT
          <span className="text-[0.5rem] text-zinc-600 opacity-60">Z</span>
        </h3>
      </div>
      <div className="widget-content">
        {/* Banner */}
        <div className="p-3 bg-[#007AFF]/5 border border-[#007AFF]/20 rounded-sm mb-3">
          <p className="text-[0.65rem] text-zinc-300 leading-relaxed italic">
            "The market rewards structure. We trade math, protect capital with the $100 Shield, and execute based on stack zones."
          </p>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 mb-3">
          <button
            onClick={() => { setTab("beginner"); setExpanded(null); }}
            className={`flex-1 py-1.5 text-[0.6rem] font-black uppercase rounded-sm transition-colors ${
              tab === "beginner" ? "bg-[#007AFF] text-white" : "bg-white/5 text-zinc-500 hover:bg-white/10"
            }`}
            data-testid="tab-beginner"
          >
            Safety First
          </button>
          <button
            onClick={() => { setTab("advanced"); setExpanded(null); }}
            className={`flex-1 py-1.5 text-[0.6rem] font-black uppercase rounded-sm transition-colors ${
              tab === "advanced" ? "bg-[#FFCC00] text-black" : "bg-white/5 text-zinc-500 hover:bg-white/10"
            }`}
            data-testid="tab-advanced"
          >
            Precision Scaling
          </button>
        </div>

        {/* Topics */}
        <div className="space-y-1.5 mb-4">
          {topics.map((topic) => {
            const isOpen = expanded === topic.id;
            const Icon = topic.icon;
            return (
              <div key={topic.id} className="border border-white/5 rounded-sm overflow-hidden" data-testid={`vault-${topic.id}`}>
                <button onClick={() => setExpanded(isOpen ? null : topic.id)} className="w-full flex items-center justify-between p-2.5 hover:bg-white/[0.03] transition-colors text-left">
                  <div className="flex items-center gap-2 min-w-0">
                    <Icon className="w-3.5 h-3.5 shrink-0" style={{ color: topic.color }} />
                    <span className="text-xs font-bold text-white truncate">{topic.title}</span>
                  </div>
                  {isOpen ? <ChevronDown className="w-3.5 h-3.5 text-zinc-500 shrink-0" /> : <ChevronRight className="w-3.5 h-3.5 text-zinc-500 shrink-0" />}
                </button>
                {isOpen && (
                  <div className="px-2.5 pb-2.5">
                    <div className="p-2.5 bg-[#0A0A0A] rounded-sm border-l-2" style={{ borderColor: topic.color }}>
                      <p className="text-[0.65rem] text-zinc-300 leading-relaxed whitespace-pre-line">{topic.content}</p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Case Studies */}
        <span className="text-[0.55rem] font-bold uppercase tracking-wider text-zinc-500 block mb-2">Documented Proofs</span>
        <div className="space-y-1.5">
          {caseStudies.map((cs) => (
            <div key={cs.id} className="p-2.5 bg-[#0A0A0A] border border-white/5 rounded-sm" data-testid={`case-${cs.id}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-bold text-white">{cs.title}</span>
                <span className="text-xs font-mono font-black" style={{ color: cs.color, textShadow: `0 0 8px ${cs.color}60` }}>
                  {cs.amount}
                </span>
              </div>
              <p className="text-[0.6rem] text-zinc-500 leading-relaxed">{cs.description}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeVault;
