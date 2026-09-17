import React from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta, Section } from "./PublicLayout";

export default function About() {
  usePageMeta(
    "About Josue | Why MNQ Scalp Stacks Exists",
    "The founder story behind MNQ Scalp Stacks: building a practice desk for MNQ and NQ traders who were drowning in indicators."
  );
  return (
    <PublicLayout h1="About the founder" kicker="Who Runs This">
      <Section testid="about-story">
        <div className="space-y-4 text-sm text-zinc-400 leading-relaxed">
          <p>
            I'm Josue. I built MNQ Scalp Stacks because most MNQ desks I saw were a pile of indicators and a hope
            that the next arrow would pay. I wanted a written order of operations I could teach and audit.
          </p>
          <p>
            The platform is a classroom and a practice desk. You load a layout, name the session, mark location,
            wait for alignment, write the risk, and review the work. Live study prompts exist so members can talk
            through the same language. They are not a substitute for your own judgment.
          </p>
          <p>
            EMA 21 and VWAP sit in the stack because they answer the two questions every scalp starts with: which
            way is the short-term spine leaning, and where is price relative to the session's average. Everything
            else is a condition, not a reason. The community lives in Discord, where every idea is written in the
            same five-step language you'll find on this site.
          </p>
          <p className="text-zinc-300 font-semibold">
            I am not your broker and I am not your adviser. If a result is published, it will include the window
            and the method, or it will not be published.
          </p>
        </div>
      </Section>

      <div className="flex flex-wrap gap-3">
        <Link to="/how-it-works" className="px-5 py-2.5 bg-[#34C759] text-black text-xs font-black rounded-sm">How the Stack Works</Link>
        <Link to="/academy" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Academy</Link>
        <Link to="/risk" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Risk Disclosure</Link>
      </div>
    </PublicLayout>
  );
}
