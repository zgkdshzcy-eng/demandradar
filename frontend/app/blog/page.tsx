import Link from "next/link";
import { ArrowRight, FileText } from "lucide-react";

import { api } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";
import { WaitlistFormI18n } from "@/components/waitlist-form-server";

export const revalidate = 600;

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://demandradar.example.com";

export const metadata = {
  title: "Blog · DemandRadar weekly archive",
  description:
    "Weekly archive of high-willingness-to-pay SaaS demand signals, scored across 9+ public sources.",
  alternates: { canonical: "/blog" },
  openGraph: {
    type: "website",
    title: "DemandRadar weekly archive",
    description:
      "Every Monday: Top-20 high-WTP pain points from 9+ public sources.",
    images: [
      "/og?kind=home&title=Weekly%20archive&subtitle=Top-20%20demand%20signals%20every%20Monday",
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og?kind=home&title=Weekly%20archive"],
  },
};

export default async function BlogPage() {
  const list = (await api.weeklyList(20)) || [];
  const locale = getLocale();
  const t = makeT(locale);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Blog",
    name: "DemandRadar weekly",
    url: `${SITE}/blog`,
    blogPost: list.map((w) => ({
      "@type": "BlogPosting",
      headline: w.title,
      datePublished: w.created_at,
      url: `${SITE}/sample?issue=${w.issue_no}`,
    })),
  };

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <script
        type="application/ld+json"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <header className="mb-10">
        <h1 className="text-3xl font-bold sm:text-4xl">{t("blog.title")}</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-400">
          {t("blog.subtitle")}
        </p>
      </header>

      {list.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-10 text-center text-sm text-slate-400">
          {t("blog.empty")}
        </div>
      ) : (
        <ul className="space-y-3">
          {list.map((w) => (
            <li
              key={w.id}
              className="flex items-start justify-between gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-5 hover:border-slate-700"
            >
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2 text-xs text-slate-500">
                  <FileText className="h-3.5 w-3.5" />
                  <span>#{w.issue_no}</span>
                  <span>·</span>
                  <span>
                    {new Date(w.period_start).toLocaleDateString()} ~{" "}
                    {new Date(w.period_end).toLocaleDateString()}
                  </span>
                </div>
                <h2 className="mt-1 font-semibold text-white">{w.title}</h2>
                <div className="mt-1 text-xs text-slate-500">
                  {w.items} pain points
                </div>
              </div>
              <Link
                href={`/sample?issue=${w.issue_no}`}
                className="inline-flex shrink-0 items-center gap-1 self-center rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-white"
              >
                {t("blog.openIssue")} <ArrowRight className="h-3 w-3" />
              </Link>
            </li>
          ))}
        </ul>
      )}

      <section className="mt-16 rounded-xl border border-slate-800 bg-slate-900/40 p-8">
        <h2 className="text-xl font-semibold">{t("blog.subscribe")}</h2>
        <div className="mt-4 max-w-md">
          <WaitlistFormI18n />
        </div>
      </section>
    </main>
  );
}
