import Link from "next/link";
import { Check, Sparkles } from "lucide-react";
import { CheckoutButton } from "@/components/checkout-button";
import { WaitlistFormI18n } from "@/components/waitlist-form-server";
import { getLocale, makeT } from "@/lib/i18n";

export const metadata = {
  title: "Pricing",
  description:
    "Three tiers: Free, Pro Weekly, and Studio Brief. First 100 subscribers lock in lifetime price.",
  alternates: { canonical: "/pricing" },
  openGraph: {
    title: "DemandRadar Pricing · from $9.9",
    description: "Three tiers: Free, Pro Weekly, and Studio Brief.",
    images: [
      "/og?kind=home&title=DemandRadar%20Pricing&subtitle=%249.9%2Fmo%20Pro%20%C2%B7%20%2429%20per%20brief",
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og?kind=home&title=DemandRadar%20Pricing"],
  },
};

interface Tier {
  nameKey: string;
  priceKey: string;
  unitKey: string;
  highlight?: boolean;
  blurbKey: string;
  featureKeys: string[];
  ctaKey: string;
  href: string;
  plan?: "weekly_pro" | "studio";
}

const TIERS: Tier[] = [
  {
    nameKey: "pricing.tier.free.name",
    priceKey: "pricing.tier.free.price",
    unitKey: "pricing.tier.free.unit",
    blurbKey: "pricing.tier.free.blurb",
    featureKeys: [
      "pricing.tier.free.f1",
      "pricing.tier.free.f2",
      "pricing.tier.free.f3",
      "pricing.tier.free.f4",
    ],
    ctaKey: "pricing.tier.free.cta",
    href: "/#waitlist",
  },
  {
    nameKey: "pricing.tier.pro.name",
    priceKey: "pricing.tier.pro.price",
    unitKey: "pricing.tier.pro.unit",
    highlight: true,
    blurbKey: "pricing.tier.pro.blurb",
    featureKeys: [
      "pricing.tier.pro.f1",
      "pricing.tier.pro.f2",
      "pricing.tier.pro.f3",
      "pricing.tier.pro.f4",
      "pricing.tier.pro.f5",
    ],
    ctaKey: "pricing.tier.pro.cta",
    href: "#",
    plan: "weekly_pro",
  },
  {
    nameKey: "pricing.tier.studio.name",
    priceKey: "pricing.tier.studio.price",
    unitKey: "pricing.tier.studio.unit",
    blurbKey: "pricing.tier.studio.blurb",
    featureKeys: [
      "pricing.tier.studio.f1",
      "pricing.tier.studio.f2",
      "pricing.tier.studio.f3",
      "pricing.tier.studio.f4",
      "pricing.tier.studio.f5",
    ],
    ctaKey: "pricing.tier.studio.cta",
    href: "/briefs",
  },
];

export default function PricingPage() {
  const locale = getLocale();
  const t = makeT(locale);
  return (
    <main className="mx-auto max-w-6xl px-6 py-16">
      <header className="mb-12 text-center">
        <h1 className="text-3xl font-bold sm:text-4xl">
          {t("pricing.title.a")}
          <span className="text-brand">{t("pricing.title.b")}</span>
        </h1>
        <p className="mx-auto mt-4 max-w-2xl text-slate-400">
          {t("pricing.subtitle")}
        </p>
      </header>

      <div className="grid gap-6 lg:grid-cols-3">
        {TIERS.map((tier) => (
          <div
            key={tier.nameKey}
            className={`flex flex-col rounded-2xl border p-6 ${
              tier.highlight
                ? "border-brand bg-gradient-to-b from-brand/10 to-slate-900"
                : "border-slate-800 bg-slate-900/40"
            }`}
          >
            <div className="flex items-baseline justify-between">
              <h2 className="text-xl font-semibold">{t(tier.nameKey)}</h2>
              {tier.highlight && (
                <span className="inline-flex items-center gap-1 rounded-full bg-brand/20 px-2 py-0.5 text-xs text-brand">
                  <Sparkles className="h-3 w-3" />
                  {t("pricing.tier.pro.eyebrow")}
                </span>
              )}
            </div>
            <div className="mt-3 flex items-baseline gap-2">
              <div className="text-3xl font-bold text-white">
                {t(tier.priceKey)}
              </div>
              <div className="text-sm text-slate-500">{t(tier.unitKey)}</div>
            </div>
            <p className="mt-3 text-sm text-slate-400">{t(tier.blurbKey)}</p>

            <ul className="mt-5 flex-1 space-y-2 text-sm text-slate-300">
              {tier.featureKeys.map((fk) => (
                <li key={fk} className="flex items-start gap-2">
                  <Check className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-400" />
                  <span>{t(fk)}</span>
                </li>
              ))}
            </ul>

            {tier.plan ? (
              <div className="mt-6">
                <CheckoutButton
                  plan={tier.plan}
                  className={`inline-flex w-full items-center justify-center gap-1.5 rounded-lg px-4 py-2.5 text-sm font-semibold transition ${
                    tier.highlight
                      ? "bg-brand text-white hover:bg-brand-dark"
                      : "border border-slate-700 text-white hover:border-slate-500"
                  } disabled:opacity-60`}
                >
                  {t(tier.ctaKey)}
                </CheckoutButton>
              </div>
            ) : (
              <Link
                href={tier.href}
                className={`mt-6 inline-flex justify-center rounded-lg px-4 py-2.5 text-sm font-semibold transition ${
                  tier.highlight
                    ? "bg-brand text-white hover:bg-brand-dark"
                    : "border border-slate-700 text-white hover:border-slate-500"
                }`}
              >
                {t(tier.ctaKey)}
              </Link>
            )}
          </div>
        ))}
      </div>

      {/* FAQ */}
      <section className="mt-20 max-w-3xl mx-auto">
        <h2 className="text-2xl font-semibold">{t("pricing.faq.title")}</h2>
        <div className="mt-6 space-y-6 text-sm">
          <Faq q={t("pricing.faq.q1")} a={t("pricing.faq.a1")} />
          <Faq q={t("pricing.faq.q2")} a={t("pricing.faq.a2")} />
          <Faq q={t("pricing.faq.q3")} a={t("pricing.faq.a3")} />
          <Faq q={t("pricing.faq.q4")} a={t("pricing.faq.a4")} />
        </div>
      </section>

      <section
        id="waitlist"
        className="mt-20 rounded-2xl border border-slate-800 bg-slate-900/60 p-10 text-center"
      >
        <h2 className="text-2xl font-semibold">{t("pricing.bottom.title")}</h2>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-400">
          {t("pricing.bottom.subtitle")}
        </p>
        <div className="mx-auto mt-6 max-w-md">
          <WaitlistFormI18n />
        </div>
      </section>
    </main>
  );
}

function Faq({ q, a }: { q: string; a: string }) {
  return (
    <details className="group rounded-lg border border-slate-800 bg-slate-900/40 p-4">
      <summary className="cursor-pointer list-none font-medium text-white">
        {q}
      </summary>
      <div className="mt-3 text-slate-400">{a}</div>
    </details>
  );
}
