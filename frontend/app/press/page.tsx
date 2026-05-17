import Link from "next/link";
import { Download, Mail } from "lucide-react";

import { getLocale, makeT } from "@/lib/i18n";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://demandradar.example.com";
const PRESS_EMAIL = process.env.NEXT_PUBLIC_PRESS_EMAIL || "press@demandradar.example.com";

export const metadata = {
  title: "Press kit · DemandRadar",
  description:
    "DemandRadar press kit: logos, screenshots, brand colors, boilerplate copy, and contact information for journalists and partners.",
  alternates: { canonical: "/press" },
  openGraph: {
    type: "website",
    title: "DemandRadar press kit",
    description: "Logos, screenshots, brand colors and boilerplate copy.",
    images: [
      "/og?kind=home&title=Press%20kit&subtitle=Logos%2C%20screenshots%2C%20boilerplate",
    ],
  },
};

export default function PressPage() {
  const locale = getLocale();
  const t = makeT(locale);

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <header className="mb-10">
        <h1 className="text-3xl font-bold sm:text-4xl">{t("press.title")}</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-400">
          {t("press.subtitle")}
        </p>
      </header>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold">{t("press.boilerplate.title")}</h2>
        <p className="mt-3 text-sm leading-relaxed text-slate-300">
          {t("press.boilerplate.body")}
        </p>
      </section>

      <section className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-lg font-semibold">{t("press.tagline.title")}</h2>
          <p className="mt-3 text-sm text-slate-300">
            EN: {t("press.tagline.en")}
          </p>
          <p className="mt-2 text-sm text-slate-300">
            ZH: {t("press.tagline.zh")}
          </p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
          <h2 className="text-lg font-semibold">{t("press.colors.title")}</h2>
          <ul className="mt-3 space-y-2 text-xs text-slate-400">
            <li className="flex items-center gap-3">
              <span className="inline-block h-5 w-5 rounded bg-brand"></span>
              <code>brand · #34d399 (emerald 400)</code>
            </li>
            <li className="flex items-center gap-3">
              <span className="inline-block h-5 w-5 rounded bg-slate-950"></span>
              <code>bg · slate 950</code>
            </li>
            <li className="flex items-center gap-3">
              <span className="inline-block h-5 w-5 rounded bg-slate-100"></span>
              <code>text · slate 100</code>
            </li>
          </ul>
        </div>
      </section>

      <section className="mt-8 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold">{t("press.assets.title")}</h2>
        <ul className="mt-4 space-y-3 text-sm text-slate-300">
          <li className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <span>{t("press.assets.logo")}</span>
            <a
              href="/og?kind=home&title=DemandRadar"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-brand hover:underline"
            >
              <Download className="h-3.5 w-3.5" /> SVG
            </a>
          </li>
          <li className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <span>{t("press.assets.og")}</span>
            <a
              href="/og?kind=home"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-xs text-brand hover:underline"
            >
              <Download className="h-3.5 w-3.5" /> PNG
            </a>
          </li>
          <li className="flex items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/40 p-3">
            <span>{t("press.assets.screenshots")}</span>
            <Link
              href="/sample"
              className="inline-flex items-center gap-1 text-xs text-brand hover:underline"
            >
              View live
            </Link>
          </li>
        </ul>
      </section>

      <section className="mt-8 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold">{t("press.contact.title")}</h2>
        <a
          href={`mailto:${PRESS_EMAIL}`}
          className="mt-3 inline-flex items-center gap-2 text-sm text-brand hover:underline"
        >
          <Mail className="h-4 w-4" /> {PRESS_EMAIL}
        </a>
        <p className="mt-3 text-xs text-slate-500">
          Site: <code className="text-slate-300">{SITE}</code>
        </p>
      </section>
    </main>
  );
}
