import Link from "next/link";
import { ArrowRight, FileText, Lock } from "lucide-react";
import { api } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";

export const metadata = {
  title: "Project briefs",
  description:
    "13-section project briefs: target user, evidence chain, MVP scope, recommended stack, monetization, risks.",
  alternates: { canonical: "/briefs" },
  openGraph: {
    title: "DemandRadar briefs · ready to build",
    description: "13 sections · evidence chain · monetization · Markdown / HTML / PDF export",
    images: [
      "/og?kind=brief&title=DemandRadar%20briefs&subtitle=13%20sections%20%C2%B7%20ready%20to%20build",
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og?kind=brief&title=DemandRadar%20briefs"],
  },
};

export const revalidate = 600;

export default async function BriefsIndexPage() {
  const data = await api.briefList(20);
  const items = data?.items || [];
  const locale = getLocale();
  const t = makeT(locale);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-10">
        <h1 className="text-3xl font-bold sm:text-4xl">{t("briefs.title")}</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-400">{t("briefs.intro")}</p>
      </header>

      {items.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-10 text-center">
          <FileText className="mx-auto h-8 w-8 text-slate-600" />
          <div className="mt-3 text-slate-400">{t("briefs.empty.title")}</div>
          <Link
            href="/pricing"
            className="mt-6 inline-flex items-center gap-1 rounded-lg border border-slate-700 px-4 py-2 text-sm hover:border-slate-500"
          >
            {t("briefs.empty.cta")} <ArrowRight className="h-4 w-4" />
          </Link>
        </div>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2">
          {items.map((b) => (
            <li
              key={b.id}
              className="flex flex-col rounded-xl border border-slate-800 bg-slate-900/40 p-5 transition hover:border-slate-700"
            >
              <div className="flex items-start justify-between gap-3">
                <h2 className="line-clamp-2 font-semibold text-white">{b.title}</h2>
                {b.total_score !== null && (
                  <span className="rounded-full bg-brand/15 px-2 py-0.5 text-xs text-brand tabular-nums">
                    {b.total_score.toFixed(0)}
                  </span>
                )}
              </div>
              {b.pain && (
                <p className="mt-2 line-clamp-2 text-sm text-slate-400">
                  {t("briefs.painPrefix")}{b.pain}
                </p>
              )}
              <p className="mt-3 line-clamp-3 text-xs text-slate-500">{b.preview}</p>
              <div className="mt-4 flex items-center justify-between text-xs text-slate-500">
                <div className="inline-flex items-center gap-1">
                  <Lock className="h-3 w-3" />
                  {t("briefs.proLockedHint")}
                </div>
                <Link
                  href={`/briefs/${b.id}`}
                  className="text-brand hover:underline"
                >
                  {t("briefs.viewPreview")} →
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
