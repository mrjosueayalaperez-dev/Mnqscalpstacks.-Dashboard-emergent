import React from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta, Section } from "./PublicLayout";

export default function Privacy() {
  usePageMeta(
    "Privacy Policy | MNQ Scalp Stacks",
    "What we collect, how Discord, TradingView, and Stripe are involved, cookies, and how to request deletion."
  );
  return (
    <PublicLayout h1="Privacy policy" kicker="Your Data">
      <Section title="What we collect" testid="privacy-collect">
        <p className="text-sm text-zinc-400 leading-relaxed">Account email and name, subscription tier, login timestamps, and anonymous page-visit counts used for site analytics. Trade journal entries and practice logs you create are stored with your account.</p>
      </Section>
      <Section title="Third parties" testid="privacy-thirdparties">
        <p className="text-sm text-zinc-400 leading-relaxed">Payments are processed by Stripe — we never see or store your card number. Community runs on Discord and charting on TradingView; both have their own privacy policies and your use of them is governed by those. Optional Google sign-in shares your name and email with us for account creation only.</p>
      </Section>
      <Section title="Cookies" testid="privacy-cookies">
        <p className="text-sm text-zinc-400 leading-relaxed">We use essential cookies for login sessions and a local identifier for de-duplicated visit counting. No third-party advertising cookies.</p>
      </Section>
      <Section title="Deletion requests" testid="privacy-deletion">
        <p className="text-sm text-zinc-400 leading-relaxed">To request account and data deletion, message the team in the members' Discord or reply to any Stripe receipt email. We delete account records within 30 days, except transaction records we must keep for accounting.</p>
      </Section>
      <div className="flex flex-wrap gap-3">
        <Link to="/terms" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Terms</Link>
        <Link to="/risk" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Risk Disclosure</Link>
      </div>
    </PublicLayout>
  );
}
