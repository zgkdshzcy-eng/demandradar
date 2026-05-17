import { getLocale, makeT } from "@/lib/i18n";

export const metadata = {
  title: "Privacy policy · DemandRadar",
  description:
    "How DemandRadar collects, uses, stores, and discloses information from subscribers and visitors.",
  alternates: { canonical: "/privacy" },
  robots: { index: true, follow: true },
};

const LAST_UPDATED = "2026-05-11";

export default function PrivacyPage() {
  const locale = getLocale();
  const t = makeT(locale);
  return (
    <main className="mx-auto max-w-3xl px-6 py-16 text-slate-200">
      <h1 className="text-3xl font-bold">Privacy Policy</h1>
      <p className="mt-2 text-xs text-slate-500">
        {t("legal.lastUpdated", { date: LAST_UPDATED })}
      </p>

      <section className="prose prose-invert mt-8 max-w-none text-sm leading-relaxed">
        <h2>1. What we collect</h2>
        <ul>
          <li>
            <strong>Account data</strong>: email address, optional name,
            referral code, sign-in timestamps.
          </li>
          <li>
            <strong>Billing data</strong>: handled by Stripe. We store the
            customer/subscription IDs returned by Stripe but never store full
            card numbers.
          </li>
          <li>
            <strong>Usage data</strong>: pages visited, IP-derived approximate
            country, UTM parameters, referral code on first visit. We use
            Google Analytics 4 (international) and Baidu Tongji (China) when
            their environment variables are configured.
          </li>
          <li>
            <strong>Email engagement</strong>: open and click signals from our
            transactional and weekly emails, used to gauge content quality.
          </li>
        </ul>

        <h2>2. How we use it</h2>
        <ul>
          <li>To deliver the weekly issue, briefs and account services you signed up for.</li>
          <li>To process payments via Stripe and prevent fraud.</li>
          <li>To improve content quality, UX and pricing.</li>
          <li>
            With your consent, to send transactional reminders (cold-start
            pings, payment-failure dunning, daily admin digest for staff
            accounts).
          </li>
        </ul>

        <h2>3. What we do not do</h2>
        <ul>
          <li>We do not sell personal data.</li>
          <li>We do not share your email with advertisers.</li>
          <li>We do not place third-party retargeting pixels.</li>
        </ul>

        <h2>4. Data retention</h2>
        <p>
          Account data is retained while your account is active and for up to
          24 months after your last login or active subscription. You can
          request deletion at any time via{" "}
          <a href="mailto:privacy@demandradar.example.com">privacy@demandradar.example.com</a>.
        </p>

        <h2>5. Sub-processors</h2>
        <ul>
          <li>Stripe (payments)</li>
          <li>Resend / SES (transactional email)</li>
          <li>Google Analytics 4 (international web analytics)</li>
          <li>Baidu Tongji (Chinese web analytics)</li>
          <li>Hosting and CDN providers (DigitalOcean / Cloudflare)</li>
        </ul>

        <h2>6. Your rights</h2>
        <p>
          You can request access to, correction of, or deletion of your data,
          and you can opt out of the weekly newsletter at any time via the
          unsubscribe link in every email. Contact{" "}
          <a href="mailto:privacy@demandradar.example.com">privacy@demandradar.example.com</a>.
        </p>

        <h2>7. Cookies</h2>
        <p>
          We use a small number of first-party cookies, including{" "}
          <code>dr_lang</code> (language preference) and <code>dr_ref</code>{" "}
          (referral attribution). Analytics providers may set their own
          cookies; you can opt out via your browser settings.
        </p>

        <h2>8. Contact</h2>
        <p>
          Questions about privacy:{" "}
          <a href="mailto:privacy@demandradar.example.com">privacy@demandradar.example.com</a>.
        </p>
      </section>
    </main>
  );
}
