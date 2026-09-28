import React from "react";
import { Link } from "react-router-dom";
import { GraduationCap, Check } from "lucide-react";
import PublicLayout from "@/pages/public/PublicLayout";

const INCLUDED = [
  "Live MNQ signal dashboard with entry / stop / targets",
  "Real-time punch alerts to Discord",
  "AI Scalp Copilot (GPT + Grok) that knows your live desk",
  "Stacked 5m + 1m charts with EMA / VWAP / RSI",
  "Community Lab — probability, expectancy, risk drills",
  "Practice journal, progress tracking & learning center",
  "Manual trade simulator with $100 daily-loss safeguard",
  "Full transparency: every punch on the record, wins AND losses",
];

export default function Membership() {
  return (
    <PublicLayout kicker="Free for everyone" h1="No plans. No paywall. Just learn.">
      <div className="max-w-3xl mx-auto px-5 py-10">
        <div className="text-center mb-10">
          <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-sm bg-[#34C759]/10 border border-[#34C759]/30 text-[#34C759] text-[0.65rem] font-black tracking-widest uppercase">
            <GraduationCap className="w-3.5 h-3.5" /> 100% free
          </span>
          <p className="text-zinc-400 text-sm md:text-base max-w-xl mx-auto mt-4">
            MNQ Scalp Stacks is now a completely free learning service. Every tool that used to sit behind Pro,
            Premium and Elite is open to anyone who wants to learn to trade with discipline.
          </p>
        </div>

        <div className="bg-[#121212] border border-[#34C759]/25 rounded-sm p-6 md:p-8 mb-8" data-testid="free-plan-card">
          <div className="flex items-baseline gap-2 mb-4">
            <span className="text-4xl font-mono font-black text-white">$0</span>
            <span className="text-zinc-500 text-sm">forever · no card required</span>
          </div>
          <ul className="space-y-2 mb-6">
            {INCLUDED.map((f) => (
              <li key={f} className="flex items-start gap-2 text-sm text-zinc-300">
                <Check className="w-4 h-4 mt-0.5 text-[#34C759] shrink-0" />{f}
              </li>
            ))}
          </ul>
          <Link
            to="/auth"
            className="block w-full text-center px-6 py-3.5 bg-[#34C759] text-black font-black rounded-sm hover:bg-[#2DB84E] transition-colors"
            data-testid="membership-free-join-btn"
          >
            CREATE YOUR FREE ACCOUNT
          </Link>
        </div>

        <p className="text-center text-[0.65rem] text-zinc-600 leading-relaxed">
          Educational simulation only — not a brokerage, not a signal-selling service, not financial advice.
          Futures trading involves substantial risk of loss and is not suitable for all investors.
        </p>
      </div>
    </PublicLayout>
  );
}
