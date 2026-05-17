import { api } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

/**
 * Live KPI strip: signals scanned, pain points scored, briefs, weekly issues.
 *
 * Buffer-style transparency: rendered on the homepage as social proof. The
 * `mrr_usd` value is intentionally omitted unless > 0 — showing $0 hurts more
 * than it helps before the first paying customer lands.
 *
 * Renders nothing while the API is unreachable so the homepage never breaks.
 */
export async function PublicStatsStrip() {
  const stats = await api.publicStats();
  if (!stats) return null;
  const locale = getLocale();
  const t = makeT(locale);

  const items: Array<[string, string]> = [
    [t("stats.signals"), fmt(stats.signals_scanned)],
    [t("stats.painPoints"), fmt(stats.pain_points_scored)],
    [t("stats.briefs"), fmt(stats.briefs)],
    [t("stats.issues"), fmt(stats.weekly_issues)],
    [t("stats.subscribers"), fmt(stats.subscribers)],
  ];
  if (stats.mrr_usd > 0) {
    items.push([t("stats.mrr"), `$${fmt(stats.mrr_usd)}`]);
  }

  return (
    <section className="border-y border-slate-800 bg-slate-950/40">
      <div className="mx-auto grid max-w-5xl grid-cols-3 gap-4 px-6 py-8 text-center sm:grid-cols-6">
        {items.map(([label, value]) => (
          <div key={label}>
            <div className="text-2xl font-bold tabular-nums text-white">
              {value}
            </div>
            <div className="mt-1 text-[11px] uppercase tracking-wide text-slate-500">
              {label}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
