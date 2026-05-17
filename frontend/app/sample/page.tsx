import Link from "next/link";
import { headers } from "next/headers";
import { ArrowRight, Mail, Lock } from "lucide-react";
import { serverFetch, type WeeklyDetail } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { WaitlistFormI18n } from "@/components/waitlist-form-server";
import { getLocale, makeT } from "@/lib/i18n";

export const metadata = {
  title: "Sample weekly issue",
  description:
    "A free preview of the latest weekly demand radar: top pain points, evidence chain, and 10-dim scoring.",
  alternates: { canonical: "/sample" },
  openGraph: {
    title: "DemandRadar Sample weekly issue",
    description: "Top 20 pain points · evidence · 10-dim scoring · every Monday 9am",
    images: [
      "/og?kind=weekly&title=Sample%20weekly%20issue&subtitle=Top%2020%20pain%20points%20%C2%B7%20evidence%20%C2%B7%2010-dim%20scoring",
    ],
  },
  twitter: {
    card: "summary_large_image",
    images: ["/og?kind=weekly&title=Sample%20weekly%20issue"],
  },
};

export const dynamic = "force-dynamic";

const FALLBACK_PREVIEW_EN = `# DemandRadar · Sample weekly issue

> Continuously scanning 9+ public sources · 3,200 raw signals collected · clustered into 48 topics

## At a glance
- **Top 3 pain points**: spanning 3 distinct topics
- **Average score**: 82.3
- **Strong WTP**: 3 items

---

## #1 · Notion is slow in some regions, urgent need for local-first two-way sync

\`Score 86\` · \`go\` · \`strong WTP\` · \`high frequency\`

**Scenario**: Heavy users hit Notion 5+ times daily; load often >10s
**Target user**: Remote knowledge workers, indie developers

> Dozens of V2EX and Weibo complaints with clear willingness to pay.

---

## #2 · Cross-border sellers need bulk negative-review analysis for Shopify

\`Score 82\` · \`go\` · \`strong WTP\` · \`high frequency\`

**Scenario**: Sellers manually read 200+ negative reviews per week
**Target user**: SMB Shopify / Amazon sellers

---

## #3 · Multi-platform publishing + unified comment-reply panel for creators

\`Score 78\` · \`go\` · \`medium WTP\` · \`high frequency\`

**Scenario**: Creators sync content across 4-5 platforms manually
**Target user**: Solo creators, small MCN studios

*Subscribe to Pro to unlock the full Top 20 + complete evidence chain.*
`;

const FALLBACK_PREVIEW_ZH = `# 独立开发者需求雷达 · 样刊

> 自动扫描 9+ 公开数据源 · 共采集 3,200 条原始信号 · 聚类出 48 个主题

## 本期速览
- **Top 3 痛点**：覆盖 3 个独立主题
- **平均总分**：82.3
- **强付费意愿**：3 条

---

## #1 · Notion 国内访问慢，急需本地优先双向同步

\`总分 86\` · \`go\` · \`strong付费意愿\` · \`频次 high\`

**场景**：每天访问 5+ 次 Notion，加载经常超 10s
**目标用户**：远程办公知识工作者、独立开发者

> 已有数十条 V2EX 与微博吐槽，付费意愿明确。

---

## #2 · 跨境卖家批量分析 Shopify 差评原因

\`总分 82\` · \`go\` · \`strong付费意愿\` · \`频次 high\`

**场景**：卖家每周需手工读 200+ 差评
**目标用户**：Shopify / Amazon 中小卖家

---

## #3 · 自媒体多平台发布与评论统一面板

\`总分 78\` · \`go\` · \`medium付费意愿\` · \`频次 high\`

**场景**：内容创作者跨 4-5 平台手工同步
**目标用户**：独立创作者、MCN 小工作室

*订阅 Pro 解锁完整 Top 20 + 完整证据链。*
`;

export default async function SamplePage() {
  const cookieHeader = headers().get("cookie");
  const issue = await serverFetch<WeeklyDetail>(
    "/api/weekly/latest",
    cookieHeader,
  );
  const locale = getLocale();
  const t = makeT(locale);
  const fallbackPreview =
    locale === "zh" ? FALLBACK_PREVIEW_ZH : FALLBACK_PREVIEW_EN;
  const md =
    (issue?.unlocked && issue?.markdown_full) ||
    issue?.markdown_preview ||
    fallbackPreview;
  const hasIssue = Boolean(issue);
  const unlocked = Boolean(issue?.unlocked);

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <header className="mb-8">
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/60 px-3 py-1 text-xs text-slate-300">
          <Mail className="h-3.5 w-3.5 text-brand" />
          {hasIssue && issue
            ? t("sample.eyebrow.issueFmt", {
                n: issue.issue_no,
                start: issue.period_start.slice(0, 10),
                end: issue.period_end.slice(0, 10),
              })
            : t("sample.eyebrow.preview")}
        </div>
        <h1 className="mt-4 text-3xl font-bold sm:text-4xl">
          {issue?.title || t("sample.heading.fallback")}
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          {t("sample.subtitle")}
        </p>
      </header>

      <article className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 sm:p-8">
        <Markdown source={md} />
      </article>

      {!unlocked && (
        <div className="mt-8 rounded-xl border border-dashed border-brand/40 bg-brand/5 p-6">
          <div className="flex items-start gap-3">
            <Lock className="mt-0.5 h-5 w-5 text-brand" />
            <div className="flex-1">
              <div className="font-medium text-white">{t("sample.locked.title")}</div>
              <div className="mt-1 text-sm text-slate-400">
                {t("sample.locked.body")}
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <Link
                  href="/pricing"
                  className="inline-flex items-center gap-1 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark"
                >
                  {t("home.cta.pricing")} <ArrowRight className="h-4 w-4" />
                </Link>
                <Link
                  href="/radar"
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:border-slate-500"
                >
                  {t("home.cta.radar")}
                </Link>
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="mt-12 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold">{t("sample.bottom.title")}</h2>
        <p className="mt-2 text-sm text-slate-400">{t("sample.bottom.body")}</p>
        <div className="mt-4">
          <WaitlistFormI18n />
        </div>
      </div>
    </main>
  );
}
