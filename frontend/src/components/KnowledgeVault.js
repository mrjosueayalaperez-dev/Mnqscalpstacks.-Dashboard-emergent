import React, { useState } from "react";
import { BookOpen, ChevronDown, ChevronRight, Zap, Shield, TrendingUp } from "lucide-react";

const topics = [
  {
    id: "roof",
    icon: TrendingUp,
    level: "Foundation",
    title: "Following the Roof (200 EMA)",
    color: "#FFCC00",
    content: `The 200 EMA is the "Roof" of the market structure. When price is below the 200 EMA, the macro trend is bearish — you are under the roof. When price is above, the sky is open.

As a Zelator, your job is to RESPECT the roof. Never fight it. If price is under the 200 EMA on the 5-min chart, your bias is SHORT or FLAT. Period.

The 200 EMA moves slowly — it's not for entries. It's for DIRECTION. Think of it as the compass. You don't steer by the compass every second, but you check it before every voyage.`
  },
  {
    id: "water",
    icon: Zap,
    level: "Intermediate",
    title: "Navigating the Water (21 EMA)",
    color: "#007AFF",
    content: `The 21 EMA is the "Water" — the current you swim in. This is your SPINE on the 1-minute chart. Every Scalp Punch signal is born from the 21 EMA.

BUY PUNCH: Price crosses ABOVE the 21 EMA while ABOVE VWAP. The water is warm — you're swimming WITH the current.

SELL PUNCH: Price crosses BELOW the 21 EMA while BELOW VWAP. The water is cold — you're riding the undertow.

When the 21 EMA is FLAT, the water is still. DO NOT SWIM. Wait for the current to form. Flat = No Punch.`
  },
  {
    id: "love",
    icon: Shield,
    level: "Critical",
    title: "The $100 Love (Capital Protection)",
    color: "#FF3B30",
    content: `The $100 Love rule is non-negotiable. It is the ATM of discipline.

You walk into the session with $100 max risk. That's it. When the Safety Sentinel hits -$100, the system LOCKS. No overrides. No revenge trades. No "one more try."

Why $100? Because it's recoverable. A -$100 day is a lesson. A -$500 day is a wound. A -$2000 day is a funeral for your account.

The math: At $2/point on MNQ with a 40-tick stop, that's $80 per trade. You get ONE clean shot with buffer. Make it count.

This rule separates the Zelator from the gambler. Love your capital. It loves you back.`
  },
  {
    id: "vwap",
    icon: TrendingUp,
    level: "Advanced",
    title: "The Institutional Level (VWAP)",
    color: "#34C759",
    content: `VWAP (Volume Weighted Average Price) is where the institutions play. It represents the average price weighted by volume — the "fair value" of the session.

When price is ABOVE VWAP: Buyers are in control. The Hydro-Pilot shows GO.
When price is BELOW VWAP: Sellers are in control. The Hydro-Pilot shows NO-GO for longs.

VWAP resets every session. It's your daily anchor. The best Scalp Punch setups happen when price crosses the 21 EMA AND is on the right side of VWAP. That's confluence. That's the Punch.

Pro tip: VWAP is strongest in the first 2 hours of the session (9:30-11:30 ET). After lunch, it gets choppy. The Zelator knows when to trade and when to WAIT.`
  },
];

const KnowledgeVault = () => {
  const [expanded, setExpanded] = useState(null);

  return (
    <div className="widget-panel col-span-1 md:col-span-2 lg:col-span-4" data-testid="knowledge-vault">
      <div className="widget-header">
        <h3 className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-[#007AFF]" />
          KNOWLEDGE VAULT
        </h3>
        <span className="text-[0.6rem] text-zinc-500">Zero to Advanced</span>
      </div>
      <div className="widget-content">
        <div className="space-y-1.5">
          {topics.map((topic) => {
            const isOpen = expanded === topic.id;
            const Icon = topic.icon;
            return (
              <div key={topic.id} className="border border-white/5 rounded-sm overflow-hidden" data-testid={`vault-${topic.id}`}>
                <button
                  onClick={() => setExpanded(isOpen ? null : topic.id)}
                  className="w-full flex items-center justify-between p-3 hover:bg-white/[0.03] transition-colors text-left"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <Icon className="w-4 h-4 shrink-0" style={{ color: topic.color }} />
                    <div className="min-w-0">
                      <span className="text-xs font-bold text-white block truncate">{topic.title}</span>
                      <span className="text-[0.55rem] text-zinc-600">{topic.level}</span>
                    </div>
                  </div>
                  {isOpen ? <ChevronDown className="w-4 h-4 text-zinc-500 shrink-0" /> : <ChevronRight className="w-4 h-4 text-zinc-500 shrink-0" />}
                </button>
                {isOpen && (
                  <div className="px-3 pb-3 pt-0">
                    <div className="p-3 bg-[#0A0A0A] rounded-sm border-l-2" style={{ borderColor: topic.color }}>
                      <p className="text-xs text-zinc-300 leading-relaxed whitespace-pre-line">{topic.content}</p>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default KnowledgeVault;
