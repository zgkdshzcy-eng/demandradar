/**
 * RSS 2.0 feed: latest weekly issues + recent briefs.
 *
 * Cached for 30 minutes (server-side) so feed readers polling every 5–10 min
 * never hit the DB. We only expose public preview content — paid markdown is
 * never rendered here.
 */
import { api } from "@/lib/api";
import { getLocale, t } from "@/lib/i18n";

export const revalidate = 1800;

const SITE =
  process.env.NEXT_PUBLIC_SITE_URL || "https://demandradar.example.com";

function escapeXml(s: string): string {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function rfc822(d: string | undefined): string {
  const date = d ? new Date(d) : new Date();
  return Number.isFinite(date.valueOf())
    ? date.toUTCString()
    : new Date().toUTCString();
}

interface RssItem {
  title: string;
  link: string;
  guid: string;
  pubDate: string;
  description: string;
  category: string;
}

function itemXml(it: RssItem): string {
  return `    <item>
      <title>${escapeXml(it.title)}</title>
      <link>${escapeXml(it.link)}</link>
      <guid isPermaLink="true">${escapeXml(it.guid)}</guid>
      <pubDate>${it.pubDate}</pubDate>
      <category>${escapeXml(it.category)}</category>
      <description><![CDATA[${it.description}]]></description>
    </item>`;
}

export async function GET() {
  const [weeklies, briefs] = await Promise.all([
    api.weeklyList(20),
    api.briefList(30),
  ]);
  const locale = getLocale();

  const items: RssItem[] = [];

  for (const w of weeklies ?? []) {
    items.push({
      title: w.title || t("rss.weeklyTitleFmt", locale, { n: w.issue_no }),
      link: `${SITE}/sample`,
      guid: `${SITE}/sample#issue-${w.issue_no}`,
      pubDate: rfc822(w.created_at),
      category: "weekly",
      description:
        `<p>${escapeXml(
          t("rss.weeklyIssueFmt", locale, {
            n: w.issue_no,
            start: w.period_start || "",
            end: w.period_end || "",
          }),
        )}</p>` +
        `<p><a href="${SITE}/sample">${escapeXml(t("rss.weeklyCta", locale))}</a> · <a href="${SITE}/pricing">${escapeXml(t("nav.pricing", locale))}</a></p>`,
    });
  }

  for (const b of briefs?.items ?? []) {
    const link = `${SITE}/briefs/${b.id}`;
    items.push({
      title: b.title,
      link,
      guid: link,
      pubDate: rfc822(b.created_at),
      category: "brief",
      description: `<p>${escapeXml(
        (b.preview || "").slice(0, 300),
      )}</p><p><a href="${link}">${escapeXml(t("rss.briefCta", locale))}</a></p>`,
    });
  }

  items.sort((a, b) => Date.parse(b.pubDate) - Date.parse(a.pubDate));

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(t("rss.title", locale))}</title>
    <link>${SITE}</link>
    <description>${escapeXml(t("rss.description", locale))}</description>
    <language>${locale === "zh" ? "zh-CN" : "en"}</language>
    <lastBuildDate>${new Date().toUTCString()}</lastBuildDate>
    <atom:link href="${SITE}/rss.xml" rel="self" type="application/rss+xml" />
${items.map(itemXml).join("\n")}
  </channel>
</rss>`;

  return new Response(xml, {
    status: 200,
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, s-maxage=1800, stale-while-revalidate=600",
    },
  });
}
