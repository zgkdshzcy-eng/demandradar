import Link from "next/link";
import { Github, Rss, Twitter, MessageCircle } from "lucide-react";
import { getLocale, makeT } from "@/lib/i18n";

const X_URL = process.env.NEXT_PUBLIC_X_URL || "https://x.com/demandradar";
const GITHUB_URL =
  process.env.NEXT_PUBLIC_GITHUB_URL || "https://github.com/demandradar";
const DISCORD_URL = process.env.NEXT_PUBLIC_DISCORD_URL || "";
const TAKEDOWN_EMAIL =
  process.env.NEXT_PUBLIC_TAKEDOWN_EMAIL || "takedown@example.com";

export function SiteFooter() {
  const locale = getLocale();
  const t = makeT(locale);
  const year = new Date().getFullYear();
  return (
    <footer className="mt-16 border-t border-slate-800 bg-slate-950/60">
      <div className="mx-auto grid max-w-6xl gap-8 px-6 py-12 text-xs text-slate-500 sm:grid-cols-2 lg:grid-cols-4">
        <div>
          <div className="text-sm font-semibold text-slate-200">
            DemandRadar
          </div>
          <p className="mt-2 max-w-sm leading-relaxed">{t("footer.tagline")}</p>
          <div className="mt-4 flex items-center gap-3">
            {X_URL && (
              <a
                href={X_URL}
                aria-label="X / Twitter"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-md border border-slate-800 p-2 hover:border-slate-600 hover:text-slate-200"
              >
                <Twitter className="h-3.5 w-3.5" />
              </a>
            )}
            {GITHUB_URL && (
              <a
                href={GITHUB_URL}
                aria-label="GitHub"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-md border border-slate-800 p-2 hover:border-slate-600 hover:text-slate-200"
              >
                <Github className="h-3.5 w-3.5" />
              </a>
            )}
            {DISCORD_URL && (
              <a
                href={DISCORD_URL}
                aria-label="Discord"
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-md border border-slate-800 p-2 hover:border-slate-600 hover:text-slate-200"
              >
                <MessageCircle className="h-3.5 w-3.5" />
              </a>
            )}
            <a
              href="/rss.xml"
              aria-label="RSS"
              className="rounded-md border border-slate-800 p-2 hover:border-slate-600 hover:text-slate-200"
            >
              <Rss className="h-3.5 w-3.5" />
            </a>
          </div>
        </div>

        <div>
          <div className="text-sm font-semibold text-slate-200">
            {t("footer.product")}
          </div>
          <ul className="mt-3 space-y-2">
            <li>
              <Link href="/radar" className="hover:text-slate-300">
                {t("nav.radar")}
              </Link>
            </li>
            <li>
              <Link href="/insights" className="hover:text-slate-300">
                {t("nav.insights")}
              </Link>
            </li>
            <li>
              <Link href="/briefs" className="hover:text-slate-300">
                {t("nav.briefs")}
              </Link>
            </li>
            <li>
              <Link href="/sample" className="hover:text-slate-300">
                {t("nav.sample")}
              </Link>
            </li>
            <li>
              <Link href="/pricing" className="hover:text-slate-300">
                {t("nav.pricing")}
              </Link>
            </li>
          </ul>
        </div>

        <div>
          <div className="text-sm font-semibold text-slate-200">
            {t("footer.company")}
          </div>
          <ul className="mt-3 space-y-2">
            <li>
              <Link href="/blog" className="hover:text-slate-300">
                {t("footer.blog")}
              </Link>
            </li>
            <li>
              <Link href="/press" className="hover:text-slate-300">
                {t("footer.press")}
              </Link>
            </li>
            <li>
              <Link href="/status" className="hover:text-slate-300">
                {t("footer.status")}
              </Link>
            </li>
            <li>
              <a href="/rss.xml" className="hover:text-slate-300">
                RSS
              </a>
            </li>
            <li>
              <a
                href={`mailto:${TAKEDOWN_EMAIL}`}
                className="hover:text-slate-300"
              >
                {t("footer.takedown")}
              </a>
            </li>
          </ul>
        </div>

        <div>
          <div className="text-sm font-semibold text-slate-200">
            {t("footer.legal")}
          </div>
          <ul className="mt-3 space-y-2">
            <li>
              <Link href="/terms" className="hover:text-slate-300">
                {t("footer.terms")}
              </Link>
            </li>
            <li>
              <Link href="/privacy" className="hover:text-slate-300">
                {t("footer.privacy")}
              </Link>
            </li>
          </ul>
        </div>
      </div>
      <div className="border-t border-slate-900 px-6 py-5 text-center text-xs text-slate-600">
        {t("footer.copyright", { year })}
      </div>
    </footer>
  );
}
