import Link from "next/link";
import { headers } from "next/headers";
import { Radar, ShieldCheck, User as UserIcon } from "lucide-react";

import { serverFetch, type MeResponse } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";
import { LocaleSwitcher } from "@/components/locale-switcher";

const LINKS: Array<{ href: string; key: string }> = [
  { href: "/radar", key: "nav.radar" },
  { href: "/insights", key: "nav.insights" },
  { href: "/sample", key: "nav.sample" },
  { href: "/briefs", key: "nav.briefs" },
  { href: "/pricing", key: "nav.pricing" },
];

export async function SiteNav() {
  const cookieHeader = headers().get("cookie");
  const me = await serverFetch<MeResponse>("/api/auth/me", cookieHeader);
  const locale = getLocale();
  const t = makeT(locale);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-800 bg-slate-950/80 backdrop-blur">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-3">
        <Link href="/" className="flex items-center gap-2 text-white">
          <Radar className="h-5 w-5 text-brand" />
          <span className="font-semibold">DemandRadar</span>
        </Link>
        <nav className="hidden items-center gap-6 text-sm text-slate-300 sm:flex">
          {LINKS.map((l) => (
            <Link key={l.href} href={l.href} className="hover:text-white">
              {t(l.key)}
            </Link>
          ))}
        </nav>
        <div className="flex items-center gap-2">
          <LocaleSwitcher current={locale} />
          {me ? (
            <>
              {me.is_admin && (
                <Link
                  href="/admin"
                  className="inline-flex items-center gap-1.5 rounded-md border border-emerald-700/60 bg-emerald-900/20 px-3 py-1.5 text-sm text-emerald-300 hover:border-emerald-500 hover:text-emerald-200"
                  title={t("nav.admin.tooltip")}
                >
                  <ShieldCheck className="h-4 w-4" />
                  <span className="hidden sm:inline">{t("nav.admin")}</span>
                </Link>
              )}
              <Link
                href="/account"
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:border-slate-500 hover:text-white"
                title={me.email}
              >
                <UserIcon className="h-4 w-4 text-brand" />
                <span className="max-w-[120px] truncate">{me.email}</span>
              </Link>
            </>
          ) : (
            <>
              <Link
                href="/login"
                className="rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:border-slate-500"
              >
                {t("nav.login")}
              </Link>
              <Link
                href="/pricing"
                className="rounded-md bg-brand px-3 py-1.5 text-sm font-medium text-white hover:bg-brand-dark"
              >
                {t("home.cta.subscribe")}
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
