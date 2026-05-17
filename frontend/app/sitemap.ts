import type { MetadataRoute } from "next";

import { serverFetch, type BriefSummary } from "@/lib/api";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://demandradar.example.com";

export const revalidate = 3600;

function entry(
  path: string,
  lastModified: Date,
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"],
  priority: number,
): MetadataRoute.Sitemap[number] {
  const url = `${SITE}${path}`;
  return {
    url,
    lastModified,
    changeFrequency,
    priority,
    alternates: {
      languages: {
        en: `${url}?lang=en`,
        "zh-CN": `${url}?lang=zh`,
        "x-default": `${url}?lang=en`,
      },
    },
  };
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const now = new Date();

  const staticEntries: MetadataRoute.Sitemap = [
    entry("/", now, "daily", 1.0),
    entry("/radar", now, "hourly", 0.9),
    entry("/sample", now, "weekly", 0.8),
    entry("/briefs", now, "daily", 0.8),
    entry("/blog", now, "daily", 0.8),
    entry("/pricing", now, "weekly", 0.7),
    entry("/insights", now, "daily", 0.85),
    entry("/press", now, "monthly", 0.5),
    entry("/status", now, "hourly", 0.4),
    entry("/terms", now, "yearly", 0.3),
    entry("/privacy", now, "yearly", 0.3),
  ];

  // Public briefs only — paid briefs are still listed (preview is public).
  const list = await serverFetch<{ items: BriefSummary[] }>(
    "/api/briefs?limit=100",
    null
  );
  const briefEntries: MetadataRoute.Sitemap = (list?.items ?? []).map((b) =>
    entry(
      `/briefs/${b.id}`,
      b.created_at ? new Date(b.created_at) : now,
      "weekly",
      0.6,
    ),
  );

  return [...staticEntries, ...briefEntries];
}
