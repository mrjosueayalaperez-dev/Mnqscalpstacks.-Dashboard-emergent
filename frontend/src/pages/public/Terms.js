import React from "react";
import { Link } from "react-router-dom";
import PublicLayout, { usePageMeta, Section } from "./PublicLayout";

export default function Terms() {
  usePageMeta(
    "Terms of Service | MNQ Scalp Stacks",
    "Account, payment, cancellation, prohibited use, and limitation of liability for the MNQ Scalp Stacks education platform."
  );
  return (
    <PublicLayout h1="Terms of service" kicker="The Rules">
      <div className="space-y-2 text-sm text-zinc-400 leading-relaxed mb-8">
        <p>These terms govern your use of MNQ Scalp Stacks, an online education and practice platform. By creating an account or purchasing a membership you agree to them.</p>
      </div>

      <Section title="Accounts" testid="terms-accounts">
        <p className="text-sm text-zinc-400 leading-relaxed">You are responsible for your account credentials and for activity under your account. One person per account. We may suspend accounts that share paid content, abuse the community, or attempt to disrupt the service.</p>
      </Section>
      <Section title="Payments and cancellation" testid="terms-payments">
        <p className="text-sm text-zinc-400 leading-relaxed">Paid memberships bill monthly through Stripe. You can cancel at any time from your Stripe receipt or billing portal; cancellation stops future billing and access continues until the end of the current paid period. Refunds for the current period are handled case by case through support — reach out in Discord before disputing a charge.</p>
      </Section>
      <Section title="Educational use only" testid="terms-education">
        <p className="text-sm text-zinc-400 leading-relaxed">All content — lessons, labs, study signals, Discord prompts, dashboards — is educational material. It is not investment advice, not a trade recommendation tailored to you, and not a managed account service. See the <Link to="/risk" className="underline">Risk Disclosure</Link>.</p>
      </Section>
      <Section title="Prohibited use" testid="terms-prohibited">
        <p className="text-sm text-zinc-400 leading-relaxed">No reselling or redistributing member content, no scraping, no representing our study signals as your own service, and no use of the platform for unlawful purposes.</p>
      </Section>
      <Section title="Limitation of liability" testid="terms-liability">
        <p className="text-sm text-zinc-400 leading-relaxed">The service is provided as-is. To the maximum extent permitted by law, MNQ Scalp Stacks is not liable for trading losses, missed opportunities, service interruptions, or third-party outages (TradingView, Discord, Stripe, market data providers). Your sole remedy for dissatisfaction is to cancel.</p>
      </Section>
      <Section title="Governing law" testid="terms-law">
        <p className="text-sm text-zinc-400 leading-relaxed">These terms are governed by the laws of the United States and the state where MNQ Scalp Stacks is organized. Disputes will be handled in that jurisdiction.</p>
      </Section>

      <div className="flex flex-wrap gap-3">
        <Link to="/risk" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Risk Disclosure</Link>
        <Link to="/privacy" className="px-5 py-2.5 border border-white/15 text-zinc-300 text-xs font-bold rounded-sm hover:bg-white/5">Privacy</Link>
      </div>
    </PublicLayout>
  );
}
