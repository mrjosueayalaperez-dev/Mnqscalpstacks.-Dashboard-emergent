import React from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta, Section } from "./PublicLayout";

const LABS = [
  { name: "Probability Lab", body: "Count outcomes. Win rate without sample size and date range is marketing. Here you learn to read a small sample, a losing streak, and why one week of punches is not a system.", status: "Live" },
  { name: "Stack Lab", body: "Drill the five-step order on historical clips and live replay. The grade is whether you followed the order, not whether the next candle paid you.", status: "Live" },
  { name: "Trade Path", body: "A sequenced path from first chart layout to first reviewed week. You do not skip to live size because a video felt exciting.", status: "Live" },
  { name: "Watch and Learn", body: "Recorded walk-throughs of session, location, and trigger. You pause, mark the chart, then compare.", status: "Live" },
  { name: "Options education", body: "Separate module. Defined-risk basics for people who also study options. Not a second signal service and not tax or broker advice.", status: "Coming soon" },
];

export default function Academy() {
  usePageMeta(
    "MNQ Learning Academy | Labs, Trade Path, and Practice",
    "Probability Lab, Stack Lab, Trade Path, Watch and Learn, and options education. A classroom sequence for MNQ and NQ traders."
  );
  return (
    <PublicLayout h1="Learning Academy" kicker="The Product">
      <p className="text-sm text-zinc-400 leading-relaxed mb-10">
        The Academy is the product. Signals are optional support. Each lab below is part of a classroom sequence
        for MNQ and NQ futures traders and students. Education only — not financial advice.
      </p>

      {LABS.map((lab) => (
        <Section key={lab.name} title={lab.name} testid={`academy-${lab.name.toLowerCase().replace(/\s/g, "-")}`}>
          <div className="p-4 bg-[#121212] border border-white/10 rounded-sm">
            <span className={`inline-block mb-2 px-2 py-0.5 text-[0.55rem] font-black rounded-sm ${lab.status === "Live" ? "bg-[#34C759]/15 text-[#34C759]" : "bg-[#FFCC00]/15 text-[#FFCC00]"}`}>
              {lab.status.toUpperCase()}
            </span>
            <p className="text-sm text-zinc-400 leading-relaxed">{lab.body}</p>
          </div>
        </Section>
      ))}

      <div className="flex flex-wrap gap-3">
        <Link to="/how-it-works" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">How the Stack Works</Link>
        <Link to="/start" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Getting Started</Link>
        <Link to="/membership" className="px-5 py-2.5 bg-[#34C759] text-black text-xs font-black rounded-sm">See Membership</Link>
      </div>
    </PublicLayout>
  );
}
