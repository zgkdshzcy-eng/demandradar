import Link from "next/link";
import { ArrowDownRight, ArrowUpRight, Download, TrendingUp } from "lucide-react";

import {
  api,
  type InsightsHeatRow,
  type InsightsMover,
} from "@/lib/api";
import { getLocale, makeT, t as t0 } from "@/lib/i18n";

const STATIC_LOCALE = "en"; // metadata is static — runtime renders use getLocale()

export const metadata = {
  title: t0("insights.title.long", STATIC_LOCALE),
  description: t0("insights.descMeta", STATIC_LOCALE),
  alternates: { canonical: "/insights" },
  openGraph: {
    title: t0("insights.ogTitle", STATIC_LOCALE),
    description: t0("insights.ogDesc", STATIC_LOCALE),
    images: [
      "/og?kind=weekly&title=Insights&subtitle=Week-over-week%20demand%20trends",
    ],
  },
};

export const revalidate = 300;

const FREE_HEAT_LIMIT = 12;
const FREE_MOVERS_LIMIT = 8;

function Sparkline({ values }: { values: number[] }) {
  const w = 120;
  const h = 28;
  const max = Math.max(1, ...values);
  const step = values.length > 1 ? w / (values.length - 1) : w;
  const points = values
    .map((v, i) => `${i * step},${h - (v / max) * (h - 4) - 2}`)
    .join(" ");
  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      className="text-brand"
      role="img"
      aria-label="weekly heat sparkline"
    >
      <polyline fill="none" stroke="currentColor" strokeWidth="1.5" points={points} />
      {values.map((v, i) => (
        <circle
          key={i}
          cx={i * step}
          cy={h - (v / max) * (h - 4) - 2}
          r={i === values.length - 1 ? 2.5 : 1.4}
          fill="currentColor"
          opacity={i === values.length - 1 ? 1 : 0.55}
        />
      ))}
    </svg>
  );
}

function MoverArrow({ delta }: { delta: number }) {
  if (delta > 0) return <ArrowUpRight className="h-4 w-4 text-emerald-400" />;
  if (delta < 0) return <ArrowDownRight className="h-4 w-4 text-rose-400" />;
  return <span className="inline-block h-4 w-4 text-slate-500">·</span>;
}

function fmtPct(p: number | null, newLabel: string) {
  if (p === null) return newLabel;
  if (Math.abs(p) >= 1000) return `${(p / 100).toFixed(0)}×`;
  return `${p > 0 ? "+" : ""}${p.toFixed(0)}%`;
}

export default async function InsightsPage() {
  const [heat, movers, sources] = await Promise.all([
    api.insightsHeat(6, 50),
    api.insightsMovers(20),
    api.insightsSources(30),
  ]);
  const locale = getLocale();
  const t = makeT(locale);

  const totalSources = Object.values(sources ?? {}).reduce((a, b) => a + b, 0);
  const sortedSources = Object.entries(sources ?? {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, 12);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-10 flex items-start gap-3">
        <TrendingUp className="mt-1 h-6 w-6 text-brand" />
        <div>
          <h1 className="text-3xl font-semibold sm:text-4xl">{t("insights.title")}</h1>
          <p className="mt-2 max-w-2xl text-sm text-slate-400">{t("insights.subtitle")}</p>
        </div>
      </header>

      <section>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t("insights.movers.title")}</h2>
          <a
            href="/api/insights/export.csv?kind=movers"
            className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-white"
          >
            <Download className="h-3.5 w-3.5" /> {t("insights.csv")}
          </a>
        </div>

        <div className="overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-left text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3 font-normal">{t("insights.col.pain")}</th>
                <th className="px-4 py-3 font-normal text-right">{t("insights.col.thisWeek")}</th>
                <th className="px-4 py-3 font-normal text-right">{t("insights.col.lastWeek")}</th>
                <th className="px-4 py-3 font-normal text-right">{t("insights.col.delta")}</th>
                <th className="px-4 py-3 font-normal text-right">{t("insights.col.score")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {(movers ?? []).slice(0, FREE_MOVERS_LIMIT).map((m: InsightsMover) => (
                <tr key={m.pain_point_id} className="text-slate-200 hover:bg-slate-900/40">
                  <td className="px-4 py-3">
                    <Link
                      href={`/insights/${m.pain_point_id}`}
                      className="font-medium hover:text-brand"
                    >
                      {m.pain}
                    </Link>
                    {m.target_user && (
                      <div className="mt-0.5 text-xs text-slate-500">
                        {t("insights.target", { name: m.target_user })}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums font-medium">{m.this_week}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-400">{m.last_week}</td>
                  <td className="px-4 py-3 text-right">
                    <span className="inline-flex items-center gap-1 tabular-nums">
                      <MoverArrow delta={m.delta} />
                      <span
                        className={
                          m.delta > 0
                            ? "text-emerald-400"
                            : m.delta < 0
                              ? "text-rose-400"
                              : "text-slate-400"
                        }
                      >
                        {fmtPct(m.delta_pct, t("insights.fmtNew"))}
                      </span>
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-slate-400">
                    {m.total_score !== null ? m.total_score.toFixed(0) : "—"}
                  </td>
                </tr>
              ))}
              {(movers?.length ?? 0) > FREE_MOVERS_LIMIT && (
                <tr>
                  <td colSpan={5} className="bg-slate-900/40 px-4 py-3 text-xs text-slate-500">
                    {t("insights.proCta.movers", { n: movers!.length })}{" "}
                    <Link href="/pricing" className="ml-1 text-brand hover:underline">
                      {t("insights.proCta.link")}
                    </Link>
                    .
                  </td>
                </tr>
              )}
              {!movers?.length && (
                <tr>
                  <td colSpan={5} className="px-4 py-8 text-center text-slate-500">
                    {t("insights.empty.movers")}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-12">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold">{t("insights.heat.title")}</h2>
          <a
            href="/api/insights/export.csv?kind=heat&weeks=6"
            className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-white"
          >
            <Download className="h-3.5 w-3.5" /> CSV
          </a>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(heat ?? []).slice(0, FREE_HEAT_LIMIT).map((h: InsightsHeatRow) => (
            <Link
              href={`/insights/${h.pain_point_id}`}
              key={h.pain_point_id}
              className="group rounded-xl border border-slate-800 bg-slate-900/40 p-4 transition hover:border-brand/40 hover:bg-slate-900/70"
            >
              <div className="flex items-start justify-between gap-3">
                <h3 className="line-clamp-2 text-sm font-medium text-white group-hover:text-brand">
                  {h.pain}
                </h3>
                {h.total_score !== null && (
                  <span className="rounded bg-brand/15 px-1.5 py-0.5 text-xs tabular-nums text-brand">
                    {h.total_score.toFixed(0)}
                  </span>
                )}
              </div>
              {h.target_user && (
                <p className="mt-1 text-xs text-slate-500">{h.target_user}</p>
              )}
              <div className="mt-3 flex items-center justify-between">
                <Sparkline values={h.weeks.map((w) => w.count)} />
                <div className="text-right text-xs text-slate-500">
                  <div className="font-mono tabular-nums text-slate-300">{h.total}</div>
                  <div>{t("insights.weeks", { n: 6 })}</div>
                </div>
              </div>
            </Link>
          ))}
          {!heat?.length && (
            <div className="col-span-full rounded-xl border border-dashed border-slate-800 px-6 py-10 text-center text-sm text-slate-500">
              {t("insights.empty.heat")}
            </div>
          )}
        </div>
        {(heat?.length ?? 0) > FREE_HEAT_LIMIT && (
          <p className="mt-3 text-xs text-slate-500">
            {t("insights.proCta.heat", { n: heat!.length })}{" "}
            <Link href="/pricing" className="ml-1 text-brand hover:underline">
              {t("insights.proCta.link")}
            </Link>
            .
          </p>
        )}
      </section>

      <section className="mt-12">
        <h2 className="text-lg font-semibold">{t("insights.sources.title")}</h2>
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-800">
          <ul className="divide-y divide-slate-800">
            {sortedSources.map(([src, n]) => {
              const pct = totalSources ? (n / totalSources) * 100 : 0;
              return (
                <li key={src} className="flex items-center gap-3 px-4 py-2.5 text-sm">
                  <span className="w-32 font-mono text-xs text-slate-400">{src}</span>
                  <div className="relative h-2 flex-1 overflow-hidden rounded-full bg-slate-800">
                    <div
                      className="absolute inset-y-0 left-0 bg-brand/70"
                      style={{ width: `${Math.max(2, pct)}%` }}
                    />
                  </div>
                  <span className="w-14 text-right text-xs tabular-nums text-slate-400">{n}</span>
                  <span className="w-12 text-right text-xs tabular-nums text-slate-500">
                    {pct.toFixed(0)}%
                  </span>
                </li>
              );
            })}
            {!sortedSources.length && (
              <li className="px-4 py-6 text-center text-sm text-slate-500">
                {t("insights.empty.sources")}
              </li>
            )}
          </ul>
        </div>
      </section>
    </main>
  );
}
