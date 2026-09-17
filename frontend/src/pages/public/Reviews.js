import React from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta } from "./PublicLayout";

export default function Reviews() {
  usePageMeta(
    "MNQ Scalp Stacks Member Feedback",
    "Verified comments from members who agreed to be quoted. We do not invent ratings or customer counts."
  );
  return (
    <PublicLayout h1="Member feedback" kicker="Verified Only">
      <div className="p-5 bg-[#121212] border border-white/10 rounded-sm mb-10" data-testid="reviews-empty-state">
        <p className="text-sm text-zinc-400 leading-relaxed">
          We only publish feedback from people who used the platform and agreed to be quoted. We do not buy reviews,
          invent star ratings, or claim hundreds of local customers.
        </p>
        <p className="text-sm text-zinc-500 leading-relaxed mt-3">
          Verified member quotes will appear here as they come in — each with the name or handle the member chose,
          the month and year, the plan they used, their exact words, and a note if they were offered anything in return.
        </p>
      </div>
      <div className="flex flex-wrap gap-3">
        <Link to="/membership" className="px-5 py-2.5 bg-[#34C759] text-black text-xs font-black rounded-sm">See Membership</Link>
        <Link to="/how-it-works" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">How It Works</Link>
        <Link to="/risk" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Risk Disclosure</Link>
      </div>
    </PublicLayout>
  );
}
