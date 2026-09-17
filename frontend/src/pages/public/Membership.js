import React from "react";
import { Link } from "react-router-dom";
import { Check, ExternalLink } from "lucide-react";
import PublicLayout, { usePageMeta } from "./PublicLayout";
import { paymentLinkFor } from "@/lib/paymentLinks";

const TIERS = [
  { id: "free", name: "Free", price: "$0", period: "", accent: "#007AFF", features: ["Core lessons and public study material", "Delayed study signals (last 3)", "Discord community access", "Member dashboard (simulator)"] , note: "Best for students starting the Trade Path" },
  { id: "pro", name: "Pro", price: "$49", period: "/mo", accent: "#FFCC00", popular: true, features: ["All Academy labs", "Real-time study-signal feed", "Discord classroom (full)", "AI trade analysis + daily briefing", "No ads"], note: "Best for active practice" },
  { id: "premium", name: "Premium", price: "$99.99", period: "/mo", accent: "#BF5AF2", features: ["Everything in Pro", "Operator bracket presets", "Live key-level alerts", "Weekly performance report"], note: "Best for a daily desk routine" },
  { id: "elite", name: "Elite", price: "$149", period: "/mo", accent: "#34C759", features: ["Everything in Premium", "Elite Discord + desk chat", "1-on-1 review sessions", "Priority signals + webhook API"], note: "Best for full desk support" },
];

export default function Membership() {
  usePageMeta(
    "MNQ Scalp Stacks Membership | Plans and What Is Included",
    "Compare membership features: Academy access, chart layout, Discord classroom, and optional study-signal feed. Cancel anytime rules are on this page."
  );
  return (
    <PublicLayout h1="Membership plans" kicker="Join The Desk">
      <p className="text-sm text-zinc-400 leading-relaxed mb-8">
        Every paid plan is billed monthly through Stripe secure checkout. Cancel anytime from your Stripe receipt or
        billing portal — access continues to the end of the paid period. MNQ Scalp Stacks is not a brokerage and no
        plan includes managed trading or a promise of profit.
      </p>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-10">
        {TIERS.map((t) => (
          <div key={t.id} className="relative p-5 bg-[#121212] border rounded-sm flex flex-col" style={{ borderColor: `${t.accent}40` }} data-testid={`membership-tier-${t.id}`}>
            {t.popular && <span className="absolute -top-2.5 left-4 px-2 py-0.5 bg-[#FFCC00] text-black text-[0.5rem] font-black rounded-sm">MOST POPULAR</span>}
            <h2 className="text-sm font-black" style={{ color: t.accent }}>{t.name}</h2>
            <p className="mb-3"><span className="text-3xl font-mono font-bold text-white">{t.price}</span><span className="text-zinc-500 text-sm">{t.period}</span></p>
            <ul className="space-y-1.5 mb-4 flex-1">
              {t.features.map((f) => (
                <li key={f} className="flex items-start gap-2 text-xs text-zinc-400">
                  <Check className="w-3 h-3 mt-0.5 shrink-0" style={{ color: t.accent }} />{f}
                </li>
              ))}
            </ul>
            <p className="text-[0.6rem] text-zinc-600 mb-3">{t.note}</p>
            {t.id === "free" ? (
              <Link to="/start" className="w-full text-center py-3 border border-white/15 text-zinc-200 text-xs font-black rounded-sm hover:bg-white/5" data-testid="membership-free-cta">
                Start Free
              </Link>
            ) : (
              <a
                href={paymentLinkFor(t.id)}
                target="_blank" rel="noopener noreferrer"
                className="w-full flex items-center justify-center gap-1.5 py-3 text-black text-xs font-black rounded-sm transition-opacity hover:opacity-90"
                style={{ background: t.accent, color: t.id === "premium" ? "#fff" : "#000" }}
                data-testid={`membership-${t.id}-cta`}
              >
                Get {t.name} — Secure Checkout <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>
        ))}
      </div>

      <p className="text-[0.65rem] text-zinc-600 mb-8">
        Secure payment by Stripe · Cancel anytime · Instant Discord invite after payment. Questions on billing or
        cancellation are answered on the <Link to="/faq" className="underline">FAQ</Link> and{" "}
        <Link to="/terms" className="underline">Terms</Link> pages.
      </p>

      <div className="flex flex-wrap gap-3">
        <Link to="/faq" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">FAQ</Link>
        <Link to="/risk" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Risk Disclosure</Link>
        <Link to="/start" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Getting Started</Link>
      </div>
    </PublicLayout>
  );
}
