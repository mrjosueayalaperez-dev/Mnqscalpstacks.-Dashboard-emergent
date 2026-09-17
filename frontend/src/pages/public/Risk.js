import React from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta, Section } from "./PublicLayout";

export default function Risk() {
  usePageMeta(
    "Risk Disclosure | MNQ Scalp Stacks",
    "Educational use only. Futures trading involves substantial risk of loss. Not a broker. Not investment advice. No guaranteed results."
  );
  return (
    <PublicLayout h1="Risk disclosure" kicker="Read This First">
      <div className="space-y-5 text-sm text-zinc-400 leading-relaxed mb-10" data-testid="risk-body">
        <p className="text-zinc-200 font-semibold">
          Futures and options trading involves substantial risk of loss and is not suitable for every person. You can
          lose more than you deposit. Hypothetical or past study results have many limitations and do not predict
          future results.
        </p>
        <p>
          MNQ Scalp Stacks provides education, practice tools, and optional classroom alerts. We are not a commodity
          trading advisor, investment adviser, broker, or dealer. Nothing here is an offer to buy or sell any futures
          contract or a recommendation tailored to you.
        </p>
        <p>
          Testimonials, if any, are individual experiences. They are not typical and they are not a result you should
          expect.
        </p>
      </div>

      <Section title="CFTC Rule 4.41 — hypothetical performance" testid="risk-cftc">
        <p className="text-xs text-zinc-500 leading-relaxed border border-white/10 bg-[#121212] rounded-sm p-4">
          HYPOTHETICAL PERFORMANCE RESULTS HAVE MANY INHERENT LIMITATIONS, SOME OF WHICH ARE DESCRIBED BELOW. NO
          REPRESENTATION IS BEING MADE THAT ANY ACCOUNT WILL OR IS LIKELY TO ACHIEVE PROFITS OR LOSSES SIMILAR TO
          THOSE SHOWN. IN FACT, THERE ARE FREQUENTLY SHARP DIFFERENCES BETWEEN HYPOTHETICAL PERFORMANCE RESULTS AND
          THE ACTUAL RESULTS SUBSEQUENTLY ACHIEVED BY ANY PARTICULAR TRADING PROGRAM. ONE OF THE LIMITATIONS OF
          HYPOTHETICAL PERFORMANCE RESULTS IS THAT THEY ARE GENERALLY PREPARED WITH THE BENEFIT OF HINDSIGHT. IN
          ADDITION, HYPOTHETICAL TRADING DOES NOT INVOLVE FINANCIAL RISK, AND NO HYPOTHETICAL TRADING RECORD CAN
          COMPLETELY ACCOUNT FOR THE IMPACT OF FINANCIAL RISK IN ACTUAL TRADING.
        </p>
      </Section>

      <div className="flex flex-wrap gap-3">
        <Link to="/terms" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Terms</Link>
        <Link to="/privacy" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Privacy</Link>
        <Link to="/faq" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">FAQ</Link>
      </div>
    </PublicLayout>
  );
}
