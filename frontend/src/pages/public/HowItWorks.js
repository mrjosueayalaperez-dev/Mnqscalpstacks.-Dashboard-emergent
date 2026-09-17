import React from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta, Section, Bullets } from "./PublicLayout";

export default function HowItWorks() {
  usePageMeta(
    "How MNQ Scalp Stacks Works | EMA, VWAP, RSI, and Alignment",
    "The MNQ stack in order: session context, location, trigger, risk, review. EMA 9, EMA 21, VWAP, RSI 14, and 1-minute / 5-minute alignment. Practice first."
  );
  return (
    <PublicLayout h1="How the stack works" kicker="The Process">
      <p className="text-sm text-zinc-400 leading-relaxed mb-10">
        A stack here is a study order, not a secret indicator pack. You name the session before you name the trade.
        This page explains the five steps and the chart tools members use on MNQ and NQ. Education only — not financial advice.
      </p>

      <Section title="The five steps" testid="hiw-five-steps">
        <Bullets items={[
          { head: "1. Session.", body: "Overnight, London overlap, or New York cash. Most noise lives outside the hours you actually study." },
          { head: "2. Location.", body: "Prior day high and low, session open, VWAP, and obvious psychological levels. No location, no idea." },
          { head: "3. Trigger.", body: "Alignment on the one-minute and five-minute charts. EMA 9 and EMA 21 for short-term spine. VWAP for session mean. RSI 14 as a condition, not a standalone signal." },
          { head: "4. Risk.", body: "Stop and size written before entry. A quiz pass is not a license to size up. Futures can lose more than the cash assigned to one idea." },
          { head: "5. Review.", body: "Screenshot and notes. If it is not written, it is not a lesson." },
        ]} />
      </Section>

      <Section title="Chart tools, plain English" testid="hiw-tools">
        <Bullets accent="#007AFF" items={[
          { head: "EMA 9 —", body: "short reaction line on the working timeframe." },
          { head: "EMA 21 —", body: "slower spine. Cross and hold matter more than a single poke." },
          { head: "VWAP —", body: "session average. Location relative to VWAP is part of context." },
          { head: "RSI 14 —", body: "condition filter. It does not replace structure." },
          { head: "1m / 5m alignment —", body: "lower timeframe trigger only when the five-minute map agrees." },
        ]} />
      </Section>

      <Section title="Practice before live size" testid="hiw-practice">
        <p className="text-sm text-zinc-400 leading-relaxed">
          Watch and Learn and the labs exist so you rehearse the order of operations. Study prompts in Discord are
          classroom examples, not orders to copy blindly.
        </p>
      </Section>

      <div className="flex flex-wrap gap-3">
        <Link to="/academy" className="px-5 py-2.5 bg-[#34C759] text-black text-xs font-black rounded-sm">Explore the Academy</Link>
        <Link to="/start" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Getting Started</Link>
        <Link to="/risk" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Risk Disclosure</Link>
      </div>
    </PublicLayout>
  );
}
