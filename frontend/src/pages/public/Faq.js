import React, { useEffect } from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta } from "./PublicLayout";

const FAQS = [
  { q: "What is MNQ Scalp Stacks?", a: "An education and practice platform for Micro Nasdaq (MNQ) and Nasdaq-100 (NQ) futures traders. Members learn a five-step stack, drill it in labs, and may receive study prompts in Discord. It is not a broker and not personalized financial advice." },
  { q: "Who is it for?", a: "Traders and students who want a written process on the one-minute and five-minute MNQ or NQ chart. It is not for anyone who needs guaranteed income." },
  { q: "Do you give live trading signals?", a: "Some memberships include a study-signal feed and Discord alerts. Those are classroom examples tied to the stack. They are not orders, not auto-execution, and not a promise that the next trade will win." },
  { q: "What is Wave Validation?", a: "Our name for checking that location, alignment, and risk agree before an idea is treated as valid. It is a checklist, not a crystal ball." },
  { q: "Which indicators does the stack use?", a: "EMA 9, EMA 21, session VWAP, RSI 14, and 1-minute / 5-minute alignment, plus session and prior-day levels. Indicators support the order of operations. They do not replace it." },
  { q: "Do I need TradingView?", a: "TradingView is recommended. Members load the MNQ Scalp Stacks Pine Script layout on a one-minute MNQ chart — the script and step-by-step webhook setup are on the member dashboard under Signal Engine → TradingView Setup." },
  { q: "How does Discord work?", a: "After checkout you get an invite. Classroom channels follow the same language as the site: session, location, trigger, risk, review." },
  { q: "How do subscriptions and cancellations work?", a: "Paid plans bill monthly through Stripe. Cancel anytime from your Stripe receipt or billing portal; access continues to the end of the paid period. Details are on the Terms page." },
  { q: "Can I get a refund?", a: "Monthly subscriptions can be cancelled at any time to stop future billing. Refunds for the current period are handled case by case through support — contact us in Discord before disputing a charge." },
  { q: "Where do you operate?", a: "This is an online platform. We serve MNQ and NQ traders and students who can access the site, TradingView, and Discord. We do not run a local storefront and we do not book in-person appointments." },
  { q: "Are results guaranteed?", a: "No. Futures can lose more than the funds you assign to an idea. Nothing on this site is a performance guarantee." },
  { q: "Is this financial advice?", a: "No. Content is education and practice. You are responsible for your own decisions and for any broker relationship you open." },
];

export default function Faq() {
  usePageMeta(
    "MNQ Scalp Stacks FAQ | Signals, Education, Billing, Risk",
    "Answers on what MNQ Scalp Stacks is, who it is for, Discord, chart access, subscriptions, cancellations, and risk. Education only."
  );

  useEffect(() => {
    const schema = {
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: FAQS.map((f) => ({
        "@type": "Question",
        name: f.q,
        acceptedAnswer: { "@type": "Answer", text: f.a },
      })),
    };
    const s = document.createElement("script");
    s.type = "application/ld+json";
    s.id = "faq-schema";
    s.textContent = JSON.stringify(schema);
    document.head.appendChild(s);
    return () => document.getElementById("faq-schema")?.remove();
  }, []);

  return (
    <PublicLayout h1="Frequently asked questions" kicker="Straight Answers">
      <div className="space-y-6 mb-10">
        {FAQS.map((f, i) => (
          <div key={f.q} data-testid={`faq-item-${i}`}>
            <h2 className="text-sm font-black text-white mb-1.5">{f.q}</h2>
            <p className="text-sm text-zinc-400 leading-relaxed">{f.a}</p>
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-3">
        <Link to="/membership" className="px-5 py-2.5 bg-[#34C759] text-black text-xs font-black rounded-sm">See Membership</Link>
        <Link to="/risk" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Risk Disclosure</Link>
        <Link to="/terms" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Terms</Link>
      </div>
    </PublicLayout>
  );
}
