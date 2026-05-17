import { getLocale, makeT } from "@/lib/i18n";

export const metadata = {
  title: "Terms of service · DemandRadar",
  description:
    "Terms of service for DemandRadar — accounts, subscriptions, refunds, acceptable use, and compliance for our public-data demand radar.",
  alternates: { canonical: "/terms" },
  robots: { index: true, follow: true },
};

const LAST_UPDATED = "2026-05-11";

export default function TermsPage() {
  const locale = getLocale();
  const t = makeT(locale);
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 text-slate-200">
      <h1 className="text-3xl font-bold">Terms of Service</h1>
      <p className="mt-2 text-xs text-slate-500">
        {t("legal.lastUpdated", { date: LAST_UPDATED })}
      </p>

      <section className="prose prose-invert mt-8 max-w-none text-sm leading-relaxed">
        <h2>1. Service overview</h2>
        <p>
          DemandRadar is a SaaS demand-research product that aggregates public
          signals from open APIs, RSS feeds and public web pages, then
          publishes weekly summaries and project briefs. The Service is
          provided by the DemandRadar team (&ldquo;we&rdquo;) to subscribers
          and visitors (&ldquo;you&rdquo;).
        </p>

        <h2>2. Accounts</h2>
        <p>
          Sign-in uses a passwordless magic-link sent to the email you provide.
          You are responsible for keeping access to that mailbox secure. We may
          suspend accounts that violate these terms or that we believe to be
          fraudulent.
        </p>

        <h2>3. Subscriptions, billing and refunds</h2>
        <ul>
          <li>Pricing is shown on the Pricing page in USD.</li>
          <li>Recurring subscriptions auto-renew until cancelled in the Stripe portal.</li>
          <li>
            Subscriptions are refundable within 7 days of payment, no questions
            asked. Per-brief one-off purchases are non-refundable once the
            unlock token is delivered, but can be swapped for another brief at
            the same tier.
          </li>
          <li>Redeem codes are non-transferable and have no cash value.</li>
        </ul>

        <h2>4. Acceptable use</h2>
        <p>You agree not to:</p>
        <ul>
          <li>Resell or republish full briefs/issues without prior written consent.</li>
          <li>Scrape or download our content with automated tools.</li>
          <li>Use the Service for any unlawful, defamatory, or harmful purpose.</li>
        </ul>

        <h2>5. Source attribution and takedown</h2>
        <p>
          We aggregate publicly accessible posts and quote ≤30 characters with
          a link back to the original source. Authors who wish to have a quote
          removed can contact <a href="mailto:takedown@demandradar.example.com">takedown@demandradar.example.com</a>;
          we will action valid requests within one business day.
        </p>

        <h2>6. Disclaimers</h2>
        <p>
          The Service is provided &ldquo;as is&rdquo;. Pain-point scores, briefs
          and recommendations are research outputs, not financial or business
          advice. You are solely responsible for any decisions you make based on
          our content.
        </p>

        <h2>7. Limitation of liability</h2>
        <p>
          To the maximum extent permitted by law, our aggregate liability for
          any claim arising out of or relating to the Service shall not exceed
          the amount you paid us in the 12 months preceding the claim.
        </p>

        <h2>8. Changes</h2>
        <p>
          We may update these terms; the &ldquo;Last updated&rdquo; date above
          reflects the latest revision. Material changes are emailed to active
          subscribers.
        </p>

        <h2>9. Contact</h2>
        <p>
          Questions: <a href="mailto:hello@demandradar.example.com">hello@demandradar.example.com</a>.
        </p>
      </section>
    </main>
  );
}
