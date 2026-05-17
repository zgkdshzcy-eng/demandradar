import Link from "next/link";
import { WaitlistFormI18n } from "@/components/waitlist-form-server";
import { PublicStatsStrip } from "@/components/public-stats-strip";
import {
  Radar,
  Zap,
  FileText,
  TrendingUp,
  ShieldCheck,
  Coins,
  ArrowRight,
} from "lucide-react";
import { api } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";

export const revalidate = 600;

type SampleRow = {
  rank: number;
  score: number;
  title: string;
  evidence: string;
  wtp: "weak" | "medium" | "strong";
};

const SAMPLE_FALLBACK_EN: SampleRow[] = [
  {
    rank: 1,
    score: 86,
    title: "Two-way local-first sync for Notion (slow connectivity regions)",
    evidence: "47 V2EX threads · 12 Zhihu posts · last 30 days",
    wtp: "strong",
  },
  {
    rank: 2,
    score: 82,
    title: "Bulk-download Shopify reviews and analyze negative-review reasons",
    evidence: "23 r/ecommerce posts · 8 Xianyu freelance gigs",
    wtp: "strong",
  },
  {
    rank: 3,
    score: 78,
    title: "Cross-platform publishing + unified comment-reply panel",
    evidence: "19 Xiaohongshu requests · 4 'wish there was' tweets on X",
    wtp: "medium",
  },
];

const SAMPLE_FALLBACK_ZH: SampleRow[] = [
  {
    rank: 1,
    score: 86,
    title: "Notion 国内访问慢 → 本地优先双向同步工具",
    evidence: "V2EX 近 30 天 47 条 / 知乎 12 条相关吐槽",
    wtp: "strong",
  },
  {
    rank: 2,
    score: 82,
    title: "跨境卖家批量下载 Shopify 评论并分析差评原因",
    evidence: "r/ecommerce 23 条 / 闲鱼 8 单代做",
    wtp: "strong",
  },
  {
    rank: 3,
    score: 78,
    title: "自媒体多平台发布 + 评论统一回复面板",
    evidence: "小红书 19 条求推荐 / X 4 条 wish there was",
    wtp: "medium",
  },
];

export default async function HomePage() {
  const live = (await api.topPainpoints(3)) || [];
  const locale = getLocale();
  const t = makeT(locale);
  const fallback = locale === "zh" ? SAMPLE_FALLBACK_ZH : SAMPLE_FALLBACK_EN;
  const tagline = t("home.tagline");
  const hl = t("home.taglineHighlight");
  const idx = tagline.indexOf(hl);
  const taglineBefore = idx >= 0 ? tagline.slice(0, idx) : tagline;
  const taglineAfter = idx >= 0 ? tagline.slice(idx + hl.length) : "";

  return (
    <main className="min-h-screen">
      <section className="relative overflow-hidden">
        <div className="mx-auto max-w-5xl px-6 pt-24 pb-16 text-center">
          <div className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/60 px-4 py-1.5 text-xs text-slate-300">
            <Radar className="h-3.5 w-3.5 text-brand" />
            {t("home.eyebrow")}
          </div>

          <h1 className="mt-6 text-4xl font-bold tracking-tight sm:text-6xl">
            {idx >= 0 ? (
              <>
                {taglineBefore}
                <span className="bg-gradient-to-r from-brand to-emerald-400 bg-clip-text text-transparent">
                  {hl}
                </span>
                {taglineAfter}
              </>
            ) : (
              tagline
            )}
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-slate-300">
            {t("home.subtitle")}
          </p>

          <div className="mx-auto mt-10 max-w-md">
            <WaitlistFormI18n />
            <p className="mt-3 text-xs text-slate-500">
              {t("home.waitlistConsent")}
            </p>
          </div>
        </div>
      </section>

      <PublicStatsStrip />

      <section className="border-t border-slate-800 bg-slate-950/60">
        <div className="mx-auto grid max-w-5xl gap-6 px-6 py-16 sm:grid-cols-3">
          <Card icon={<Zap className="h-5 w-5" />} title={t("home.cards.mvp.title")}>
            {t("home.cards.mvp.body")}
          </Card>
          <Card
            icon={<FileText className="h-5 w-5" />}
            title={t("home.cards.brief.title")}
          >
            {t("home.cards.brief.body")}
          </Card>
          <Card
            icon={<TrendingUp className="h-5 w-5" />}
            title={t("home.cards.revenue.title")}
          >
            {t("home.cards.revenue.body")}
          </Card>
          <Card
            icon={<Coins className="h-5 w-5" />}
            title={t("home.cards.pricing.title")}
          >
            {t("home.cards.pricing.body")}
          </Card>
          <Card
            icon={<ShieldCheck className="h-5 w-5" />}
            title={t("home.cards.compliant.title")}
          >
            {t("home.cards.compliant.body")}
          </Card>
          <Card icon={<Radar className="h-5 w-5" />} title={t("home.cards.dogfood.title")}>
            {t("home.cards.dogfood.body")}
          </Card>
        </div>
      </section>

      <section className="border-t border-slate-800">
        <div className="mx-auto max-w-3xl px-6 py-16">
          <div className="flex items-center justify-between">
            <h2 className="text-2xl font-semibold">
              {live.length > 0 ? t("home.live.title") : t("home.live.fallbackTitle")}
            </h2>
            <Link href="/radar" className="text-sm text-brand hover:underline">
              {t("home.live.viewFull")} →
            </Link>
          </div>
          <ol className="mt-6 space-y-4 text-sm text-slate-300">
            {(live.length > 0
              ? live.slice(0, 3).map<SampleRow>((p, i) => {
                  const label = p.cluster_label || t("home.live.standalone");
                  const evidence =
                    p.evidence?.length > 0
                      ? t("home.live.evidenceCount", {
                          count: p.evidence.length,
                          label,
                        })
                      : t("home.live.evidenceFallback", { label });
                  const wtpRaw = p.willingness_to_pay_signal as
                    | "weak"
                    | "medium"
                    | "strong"
                    | undefined;
                  const wtp = (["weak", "medium", "strong"] as const).includes(
                    wtpRaw as never,
                  )
                    ? (wtpRaw as "weak" | "medium" | "strong")
                    : "medium";
                  return {
                    rank: i + 1,
                    score: Math.round(p.total_score || 0),
                    title: p.pain,
                    evidence,
                    wtp,
                  };
                })
              : fallback
            ).map((it: SampleRow) => (
              <SampleItem key={it.rank} {...it} t={t} />
            ))}
          </ol>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href="/sample"
              className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-4 py-2 text-sm hover:border-slate-500"
            >
              {t("home.live.readSample")}
            </Link>
            <Link
              href="/pricing"
              className="inline-flex items-center gap-1 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark"
            >
              {t("home.cta.pricing")} <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          {live.length === 0 && (
            <p className="mt-4 text-xs text-slate-500">{t("home.live.note")}</p>
          )}
        </div>
      </section>
    </main>
  );
}

function Card({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-5">
      <div className="flex items-center gap-2 text-brand">
        {icon}
        <span className="text-sm font-medium text-white">{title}</span>
      </div>
      <p className="mt-2 text-sm text-slate-400">{children}</p>
    </div>
  );
}

function SampleItem({
  rank,
  score,
  title,
  evidence,
  wtp,
  t,
}: {
  rank: number;
  score: number;
  title: string;
  evidence: string;
  wtp: "weak" | "medium" | "strong";
  t: (key: string, vars?: Record<string, string | number>) => string;
}) {
  const wtpColor = {
    weak: "text-slate-400",
    medium: "text-amber-400",
    strong: "text-emerald-400",
  }[wtp];
  return (
    <li className="flex items-start gap-4 rounded-lg border border-slate-800 bg-slate-900/40 p-4">
      <div className="text-2xl font-bold text-slate-600">#{rank}</div>
      <div className="flex-1">
        <div className="font-medium text-white">{title}</div>
        <div className="mt-1 text-xs text-slate-500">{evidence}</div>
      </div>
      <div className="text-right">
        <div className="text-lg font-semibold text-brand">{score}</div>
        <div className={`text-xs ${wtpColor}`}>{t(`wtp.${wtp}`)}</div>
      </div>
    </li>
  );
}
