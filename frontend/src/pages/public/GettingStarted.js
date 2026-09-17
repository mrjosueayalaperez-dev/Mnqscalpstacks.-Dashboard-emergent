import React from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta, Bullets } from "./PublicLayout";

export default function GettingStarted() {
  usePageMeta(
    "Getting Started with MNQ Scalp Stacks",
    "First-week checklist: risk page, chart layout, Lesson 1, five practice ideas, Discord intro."
  );
  return (
    <PublicLayout h1="Getting started" kicker="Your First Week">
      <p className="text-sm text-zinc-400 leading-relaxed mb-8">
        The first week is a checklist, not a race to live size. Work through these five steps in order.
      </p>
      <div className="mb-10" data-testid="start-checklist">
        <Bullets items={[
          { head: "1. Read the risk page.", body: "If you cannot accept that futures lose money, stop here." },
          { head: "2. Load the chart.", body: "Create or log into TradingView and load the MNQ Scalp Stacks layout on a one-minute chart. The Pine Script and setup steps are on the member dashboard under Signal Engine → TradingView Setup." },
          { head: "3. Join Discord.", body: "Use the member invite you receive after signup or checkout." },
          { head: "4. Finish Lesson 1.", body: "Complete Academy Lesson 1 and one Stack Lab drill." },
          { head: "5. Log five practice ideas.", body: "Each with session, location, trigger, risk, and a screenshot. Do not increase size because a drill felt good." },
        ]} />
      </div>
      <div className="flex flex-wrap gap-3">
        <Link to="/risk" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Risk Disclosure</Link>
        <Link to="/academy" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Academy</Link>
        <Link to="/membership" className="px-5 py-2.5 bg-[#34C759] text-black text-xs font-black rounded-sm">Pick a Plan</Link>
      </div>
    </PublicLayout>
  );
}
