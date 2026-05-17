import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, Download, ExternalLink } from "lucide-react";

import { api, type PainPoint, type InsightsTimelinePoint } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";

interface PageProps {
  params: { id: string };
}

export const revalidate = 300;

export async function generateMetadata({ params }: PageProps) {
  const id = Number(params.id);
  if (!Number.isFinite(id)) return { title: "Insights" };
  const pp = await api.painpoint(id);
  if (!pp) return { title: "Insights" };
  return {
    title: `${pp.pain} · evidence timeline`,
    description: `Reverse-chronological evidence aggregated by source. Target: ${pp.target_user || "—"}.`,
    alternates: { canonical: `/insights/${id}` },
  };
}

const SOURCE_LABEL: Record<string, string> = {
  hn: "Hacker News",
  reddit: "Reddit",
  v2ex: "V2EX",
  producthunt: "Product Hunt",
  github_trending: "GitHub Trending",
  google_trends: "Google Trends",
  lobsters: "Lobste.rs",
  indiehackers: "IndieHackers",
  weibo: "Weibo Hot",
};

function fmtDate(s: string, locale: string): string {
  const d = new Date(s);
  return Number.isFinite(d.valueOf())
    ? d.toLocaleDateString(locale === "zh" ? "zh-CN" : "en-US", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
      })
    : s;
}

export default async function InsightsDetailPage({ params }: PageProps) {
  const id = Number(params.id);
  if (!Number.isFinite(id)) return notFound();

  const [pp, timeline] = await Promise.all([
    api.painpoint(id) as Promise<PainPoint | null>,
    api.insightsTimeline(id, 80),
  ]);
  if (!pp) return notFound();

  const locale = getLocale();
  const t = makeT(locale);

  const groups = new Map<string, InsightsTimelinePoint[]>();
  for (const tp of timeline ?? []) {
    const d = new Date(tp.posted_at);
    const key = `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(tp);
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <Link
        href="/insights"
        className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("insights.detail.back")}
      </Link>

      <header className="mt-6">
        <h1 className="text-3xl font-semibold sm:text-4xl">{pp.pain}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          {pp.total_score !== null && pp.total_score !== undefined && (
            <span className="rounded-full bg-brand/15 px-2 py-0.5 text-brand tabular-nums">
              {t("insights.detail.totalScore", { n: pp.total_score.toFixed(0) })}
            </span>
          )}
          {pp.target_user && (
            <span>
              {t("insights.detail.targetPrefix")}{pp.target_user}
            </span>
          )}
          {pp.go_no_go && (
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono uppercase">
              {pp.go_no_go}
            </span>
          )}
        </div>
        <p className="mt-2 text-sm text-slate-400">
          {t("insights.detail.intro", { n: timeline?.length ?? 0 })}
        </p>
        <div className="mt-4 flex gap-3">
          <a
            href={`/api/insights/export.csv?kind=timeline&painpoint_id=${pp.id}`}
            className="inline-flex items-center gap-1 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-white"
          >
            <Download className="h-3.5 w-3.5" /> {t("insights.detail.csv")}
          </a>
          <Link
            href={`/briefs?pp=${pp.id}`}
            className="inline-flex items-center gap-1 rounded-md border border-slate-700 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-white"
          >
            {t("insights.detail.relatedBriefs")} →
          </Link>
        </div>
      </header>

      <section className="mt-10">
        {!timeline?.length && (
          <p className="rounded-xl border border-dashed border-slate-800 px-6 py-10 text-center text-sm text-slate-500">
            {t("insights.detail.empty")}
          </p>
        )}
        {[...groups.entries()].map(([month, items]) => (
          <div key={month} className="mb-10">
            <h2 className="sticky top-0 mb-3 bg-slate-950/95 py-2 text-xs font-mono uppercase tracking-wider text-slate-500 backdrop-blur">
              {t("insights.detail.monthCount", { month, n: items.length })}
            </h2>
            <ol className="border-l border-slate-800 pl-4">
              {items.map((tp) => (
                <li key={tp.raw_signal_id} className="relative pb-6 pl-4">
                  <span className="absolute -left-1.5 top-1 h-2 w-2 rounded-full bg-brand/80" />
                  <div className="flex flex-wrap items-center gap-2 text-xs text-slate-500">
                    <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono">
                      {SOURCE_LABEL[tp.source] || tp.source}
                    </span>
                    <span>{fmtDate(tp.posted_at, locale)}</span>
                    {tp.score > 0 && (
                      <span className="tabular-nums text-slate-400">
                        ↑ {tp.score}
                      </span>
                    )}
                    {tp.url && (
                      <a
                        href={tp.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-auto inline-flex items-center gap-1 text-brand hover:underline"
                      >
                        {t("insights.detail.openOrig")}
                        <ExternalLink className="h-3 w-3" />
                      </a>
                    )}
                  </div>
                  {tp.title && (
                    <p className="mt-1.5 text-sm font-medium text-slate-200">
                      {tp.title}
                    </p>
                  )}
                  {tp.text && tp.text !== tp.title && (
                    <p className="mt-1 line-clamp-3 text-sm text-slate-400">
                      {tp.text}
                    </p>
                  )}
                </li>
              ))}
            </ol>
          </div>
        ))}
      </section>
    </main>
  );
}
