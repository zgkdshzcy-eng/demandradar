import Link from "next/link";
import { CheckCircle2, AlertTriangle, XCircle, Activity } from "lucide-react";

import { api } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";

export const revalidate = 60;
export const dynamic = "force-dynamic";

export const metadata = {
  title: "System status · DemandRadar",
  description:
    "Live health of DemandRadar's collectors, pipeline and weekly publishing pipeline. We publish degraded states proactively.",
  alternates: { canonical: "/status" },
  openGraph: {
    title: "DemandRadar status",
    description: "Public collector health + recent weekly publishing history.",
    images: ["/og?kind=home&title=System%20status"],
  },
};

const STATE_STYLE: Record<
  "healthy" | "degraded" | "down",
  { dot: string; label: string; icon: React.ReactNode }
> = {
  healthy: {
    dot: "bg-emerald-400",
    label: "text-emerald-300",
    icon: <CheckCircle2 className="h-4 w-4 text-emerald-400" />,
  },
  degraded: {
    dot: "bg-amber-400",
    label: "text-amber-300",
    icon: <AlertTriangle className="h-4 w-4 text-amber-400" />,
  },
  down: {
    dot: "bg-rose-400",
    label: "text-rose-300",
    icon: <XCircle className="h-4 w-4 text-rose-400" />,
  },
};

export default async function StatusPage() {
  const status = await api.publicStatus();
  const locale = getLocale();
  const t = makeT(locale);

  const overall = status?.overall ?? "degraded";
  const cls = STATE_STYLE[overall];

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-10 flex items-center gap-3">
        <Activity className="h-6 w-6 text-brand" />
        <div>
          <h1 className="text-3xl font-bold">{t("status.title")}</h1>
          <div className="mt-1 flex items-center gap-2 text-sm">
            <span className={`inline-block h-2 w-2 rounded-full ${cls.dot}`} />
            <span className={cls.label}>{t(`status.overall.${overall}`)}</span>
          </div>
        </div>
      </header>

      <section className="rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold">{t("status.sources.title")}</h2>
        {!status || status.sources.length === 0 ? (
          <p className="mt-3 text-sm text-slate-400">
            {t("status.sources.empty")}
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-slate-800">
            {status.sources.map((s) => {
              const style = STATE_STYLE[s.state];
              return (
                <li
                  key={s.name}
                  className="flex items-start justify-between gap-3 py-3 text-sm"
                >
                  <div className="flex items-center gap-3">
                    {style.icon}
                    <div>
                      <div className="font-medium text-white">{s.name}</div>
                      {s.last_error && (
                        <div className="mt-0.5 max-w-md truncate text-xs text-slate-500">
                          {s.last_error}
                        </div>
                      )}
                    </div>
                  </div>
                  <div className={`text-xs ${style.label}`}>
                    {s.consecutive_failures > 0
                      ? t("status.failsCount", {
                          n: s.consecutive_failures,
                        })
                      : t("status.healthy")}
                    {s.interval_mult > 1 && (
                      <span className="ml-2 text-slate-500">
                        ×{s.interval_mult}
                      </span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
        {status?.last_signal_at && (
          <p className="mt-4 text-xs text-slate-500">
            {t("status.lastSignal", {
              ts: new Date(status.last_signal_at).toLocaleString(),
            })}
          </p>
        )}
      </section>

      <section className="mt-8 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold">{t("status.issues.title")}</h2>
        {!status || status.recent_issues.length === 0 ? (
          <p className="mt-3 text-sm text-slate-400">
            {t("status.issues.empty")}
          </p>
        ) : (
          <ul className="mt-4 divide-y divide-slate-800 text-sm">
            {status.recent_issues.map((w) => (
              <li
                key={w.issue_no}
                className="flex items-center justify-between gap-3 py-3"
              >
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-white">#{w.issue_no}</div>
                  <div className="truncate text-xs text-slate-500">
                    {w.title}
                  </div>
                </div>
                <div className="text-right text-xs text-slate-500">
                  <div>
                    {new Date(w.period_start).toLocaleDateString()} ~{" "}
                    {new Date(w.period_end).toLocaleDateString()}
                  </div>
                  <div className="mt-0.5 text-slate-600">
                    {w.items} pain points
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      <p className="mt-8 text-center text-xs text-slate-500">
        {t("status.footnote")}{" "}
        <Link href="/blog" className="text-brand hover:underline">
          {t("status.archiveLink")}
        </Link>
      </p>
    </main>
  );
}
