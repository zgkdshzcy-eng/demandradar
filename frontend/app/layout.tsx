import type { Metadata } from "next";
import { Suspense } from "react";
import "./globals.css";
import { SiteNav } from "@/components/site-nav";
import { SiteFooter } from "@/components/site-footer";
import { ReferralCookie } from "@/components/referral-cookie";
import { Analytics } from "@/components/analytics";
import { getLocale } from "@/lib/i18n";

const SITE = process.env.NEXT_PUBLIC_SITE_URL || "https://demandradar.example.com";

const languageAlternates = {
  en: "/?lang=en",
  "zh-CN": "/?lang=zh",
  "x-default": "/?lang=en",
};

export const metadata: Metadata = {
  metadataBase: new URL(SITE),
  title: {
    default: "DemandRadar · A demand radar for indie hackers",
    template: "%s · DemandRadar",
  },
  description:
    "We continuously scan 9+ public sources and ship the Top-20 high-willingness-to-pay pain points each week, with a 13-section brief you can build over a weekend.",
  keywords: [
    "demand mining",
    "indie hacker",
    "indie hackers",
    "Reddit",
    "Hacker News",
    "weekly digest",
    "project brief",
    "DemandRadar",
  ],
  authors: [{ name: "DemandRadar" }],
  alternates: {
    canonical: "/",
    languages: languageAlternates,
    types: {
      "application/rss+xml": [
        { url: "/rss.xml", title: "DemandRadar · weekly + briefs" },
      ],
    },
  },
  openGraph: {
    type: "website",
    siteName: "DemandRadar",
    locale: "en_US",
    alternateLocale: "zh_CN",
    url: SITE,
    title: "DemandRadar · A demand radar for indie hackers",
    description:
      "Top-20 high-willingness-to-pay pain points each week, with build-ready briefs.",
    images: [
      {
        url: "/og?kind=home&title=DemandRadar&subtitle=Demand%20radar%20for%20indie%20hackers",
        width: 1200,
        height: 630,
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: "DemandRadar · A demand radar for indie hackers",
    description: "Automated demand mining · weekly digest · build-ready briefs",
    images: ["/og?kind=home"],
  },
  robots: { index: true, follow: true },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = getLocale();
  return (
    <html lang={locale === "zh" ? "zh-CN" : "en"}>
      <body>
        <ReferralCookie />
        <SiteNav />
        {children}
        <SiteFooter />
        <Suspense fallback={null}>
          <Analytics />
        </Suspense>
      </body>
    </html>
  );
}
