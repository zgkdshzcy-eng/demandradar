import Link from "next/link";
import { headers } from "next/headers";
import { notFound } from "next/navigation";
import { ArrowRight, ArrowLeft, Lock, ShoppingBag } from "lucide-react";
import { api, serverFetch, type BriefDetail } from "@/lib/api";
import { Markdown } from "@/components/markdown";
import { CheckoutButton } from "@/components/checkout-button";
import { ShareBar } from "@/components/share-bar";
import { ShareUnlockButton } from "@/components/share-unlock-button";
import { getLocale, makeT, t as tRaw } from "@/lib/i18n";

export const dynamic = "force-dynamic";

interface PageProps {
  params: { id: string };
  searchParams?: { token?: string };
}

export async function generateMetadata({ params }: PageProps) {
  const id = Number(params.id);
  if (!Number.isFinite(id)) return { title: "Brief" };
  const b = await api.brief(id);
  if (!b) return { title: "Brief" };
  const title = b.title;
  const description = (b.preview || "").slice(0, 158);
  const ogUrl = `/og?kind=brief&title=${encodeURIComponent(title)}&subtitle=${encodeURIComponent(b.pain || "Ready-to-build brief")}`;
  return {
    title,
    description,
    alternates: { canonical: `/briefs/${id}` },
    openGraph: {
      type: "article",
      title,
      description,
      url: `/briefs/${id}`,
      images: [{ url: ogUrl, width: 1200, height: 630 }],
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogUrl],
    },
  };
}

export default async function BriefDetailPage({ params, searchParams }: PageProps) {
  const id = Number(params.id);
  if (!Number.isFinite(id)) return notFound();

  const cookieHeader = headers().get("cookie");
  const qs = searchParams?.token
    ? `?x_unlock_token=${encodeURIComponent(searchParams.token)}`
    : "";
  const b = await serverFetch<BriefDetail>(`/api/briefs/${id}${qs}`, cookieHeader);
  if (!b) return notFound();

  const locale = getLocale();
  const t = makeT(locale);

  const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://demandradar.example.com";
  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: b.title,
    description: (b.preview || "").slice(0, 200),
    datePublished: b.created_at,
    author: { "@type": "Organization", name: "DemandRadar" },
    publisher: { "@type": "Organization", name: "DemandRadar", url: SITE },
    mainEntityOfPage: { "@type": "WebPage", "@id": `${SITE}/briefs/${b.id}` },
  };

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <script
        type="application/ld+json"
        // eslint-disable-next-line react/no-danger
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />
      <Link
        href="/briefs"
        className="inline-flex items-center gap-1 text-sm text-slate-400 hover:text-white"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("brief.detail.back")}
      </Link>

      <header className="mt-6 mb-8">
        <h1 className="text-3xl font-bold sm:text-4xl">{b.title}</h1>
        <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-500">
          {b.total_score !== null && b.total_score !== undefined && (
            <span className="rounded-full bg-brand/15 px-2 py-0.5 text-brand tabular-nums">
              {t("brief.detail.totalScore", { n: b.total_score.toFixed(0) })}
            </span>
          )}
          {b.pain && (
            <span>
              {t("brief.detail.painPrefix")}{b.pain}
            </span>
          )}
          {b.unlocked && (
            <span className="text-emerald-400">{t("brief.detail.unlocked")}</span>
          )}
        </div>
        <div className="mt-5">
          <ShareBar
            url={`${SITE}/briefs/${b.id}`}
            title={b.title}
            summary={b.preview || ""}
            dict={{
              "share.label": tRaw("share.label", locale),
              "share.copy": tRaw("share.copy", locale),
              "share.copied": tRaw("share.copied", locale),
            }}
          />
        </div>
      </header>

      <article className="rounded-xl border border-slate-800 bg-slate-900/40 p-6 sm:p-8">
        {b.unlocked && b.markdown ? (
          <Markdown source={b.markdown} />
        ) : (
          <Markdown source={b.preview + "\n\n..."} />
        )}
      </article>

      {!b.unlocked && (
        <div className="mt-8 rounded-xl border border-dashed border-brand/40 bg-brand/5 p-6">
          <div className="flex items-start gap-3">
            <Lock className="mt-0.5 h-5 w-5 text-brand" />
            <div className="flex-1">
              <div className="font-medium text-white">{t("brief.detail.locked.title")}</div>
              <div className="mt-1 text-sm text-slate-400">
                {t("brief.detail.locked.body")}
              </div>
              <div className="mt-4 flex flex-wrap gap-3">
                <CheckoutButton
                  plan="brief_oneoff"
                  briefId={b.id}
                  className="inline-flex items-center gap-1 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
                >
                  <ShoppingBag className="h-4 w-4" />
                  {t("brief.detail.unlockOne")}
                </CheckoutButton>
                <ShareUnlockButton briefId={b.id} className="w-full justify-center" />
                <CheckoutButton
                  plan="weekly_pro"
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 hover:border-slate-500 disabled:opacity-60"
                >
                  {t("brief.detail.unlockAll")} <ArrowRight className="h-4 w-4" />
                </CheckoutButton>
              </div>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
