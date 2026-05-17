import Link from "next/link";
import { TrendingUp, ArrowRight, Lock } from "lucide-react";
import { api, type PainPoint } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";

export const metadata = {
  title: "Live radar",
  description:
    "Top-scored pain points across 9+ public sources, ranked by 10-dim score, updated in real time.",
  alternates: { canonical: "/radar" },
  openGraph: {
    title: "Live demand radar · DemandRadar",
    description: "Top 20 high-WTP pain points · sourced from HN/Reddit/V2EX/PH/GH/Trends",
    images: [
      "/og?kind=weekly&title=Live%20radar&subtitle=Top%2020%20high-WTP%20pain%20points",
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og?kind=weekly&title=Live%20radar"],
  },
};

export const revalidate = 300;
const FREE_TIER_LIMIT = 10;

export default async function RadarPage() {
  const items = (await api.topPainpoints(20)) || [];
  const locale = getLocale();
  const t = makeT(locale);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-10">
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1 text-xs text-slate-300">
          <TrendingUp className="h-3.5 w-3.5 text-brand" />
          {t("radar.eyebrow")}
        </div>
        <h1 className="mt-4 text-3xl font-bold sm:text-4xl">
          {t("radar.title.full", { n: items.length || 20 })}
        </h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-400">
          {t("radar.subtitle.full", { limit: FREE_TIER_LIMIT })}
        </p>
      </header>

      {items.length === 0 ? (
        <Empty t={t} />
      ) : (
        <ol className="space-y-4">
          {items.slice(0, FREE_TIER_LIMIT).map((p, idx) => (
            <PainCard key={p.id} pp={p} rank={idx + 1} t={t} />
          ))}
          {items.length > FREE_TIER_LIMIT && (
            <UpgradeRow remaining={items.length - FREE_TIER_LIMIT} t={t} />
          )}
        </ol>
      )}
    </main>
  );
}

type T = (key: string, vars?: Record<string, string | number>) => string;

function PainCard({ pp, rank, t }: { pp: PainPoint; rank: number; t: T }) {
  const wtp = pp.willingness_to_pay_signal;
  const wtpColor =
    wtp === "strong"
      ? "text-emerald-400"
      : wtp === "medium"
        ? "text-amber-400"
        : "text-slate-400";

  return (
    <li className="flex items-start gap-4 rounded-xl border border-slate-800 bg-slate-900/40 p-5 transition hover:border-slate-700">
      <div className="text-2xl font-bold text-slate-600 tabular-nums">#{rank}</div>
      <div className="flex-1 min-w-0">
        <div className="font-medium text-white">{pp.pain}</div>
        {pp.scenario && (
          <p className="mt-1 line-clamp-2 text-sm text-slate-400">
            <span className="text-slate-500">{t("radar.scenario")}</span>
            {pp.scenario}
          </p>
        )}
        {pp.target_user && (
          <p className="mt-1 text-xs text-slate-500">
            {t("radar.targetUser")}{pp.target_user}
          </p>
        )}
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          {pp.cluster_label && (
            <span className="rounded-full bg-slate-800 px-2 py-0.5 text-slate-400">
              {pp.cluster_label}
            </span>
          )}
          <span className={wtpColor}>
            {t("radar.wtp")} {t(`wtp.${wtp}`)}
          </span>
          <span className="text-slate-500">·</span>
          <span className="text-slate-400">
            {t("radar.frequency")} {pp.frequency_signal}
          </span>
          {pp.evidence?.length > 0 && (
            <>
              <span className="text-slate-500">·</span>
              <span className="text-slate-400">
                {t("radar.evidenceCount", { count: pp.evidence.length })}
              </span>
            </>
          )}
        </div>
      </div>
      <div className="text-right">
        <div className="text-2xl font-bold text-brand tabular-nums">
          {pp.total_score?.toFixed(0) ?? "-"}
        </div>
        <div className="text-xs text-slate-500">/100</div>
      </div>
    </li>
  );
}

function UpgradeRow({ remaining, t }: { remaining: number; t: T }) {
  return (
    <li className="flex items-center justify-between rounded-xl border border-dashed border-brand/40 bg-brand/5 p-5">
      <div className="flex items-center gap-3">
        <Lock className="h-5 w-5 text-brand" />
        <div>
          <div className="font-medium text-white">
            {t("radar.upgrade.title", { remaining })}
          </div>
          <div className="text-xs text-slate-400">{t("radar.upgrade.body")}</div>
        </div>
      </div>
      <Link
        href="/pricing"
        className="inline-flex items-center gap-1 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark"
      >
        {t("home.cta.pricing")} <ArrowRight className="h-4 w-4" />
      </Link>
    </li>
  );
}

function Empty({ t }: { t: T }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-10 text-center">
      <div className="text-slate-400">{t("radar.empty.title")}</div>
      <div className="mt-2 text-xs text-slate-500">{t("radar.empty.body")}</div>
      <Link
        href="/pricing"
        className="mt-6 inline-flex items-center gap-1 rounded-lg border border-slate-700 px-4 py-2 text-sm hover:border-slate-500"
      >
        {t("radar.empty.cta")} <ArrowRight className="h-4 w-4" />
      </Link>
    </div>
  );
}
