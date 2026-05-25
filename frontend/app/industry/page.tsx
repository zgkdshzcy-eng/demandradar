import Link from "next/link";
import { TrendingUp, ArrowRight, Building2, Zap } from "lucide-react";
import { api } from "@/lib/api";
import { getLocale, makeT } from "@/lib/i18n";

export const metadata = {
  title: "Industry Pain Rankings",
  description: "Compare pain point intensity across industries. See which sectors have the most urgent unsolved problems.",
  alternates: { canonical: "/industry" },
  openGraph: {
    title: "Industry Pain Rankings · DemandRadar",
    description: "Which industries hurt the most? Real-time benchmarking.",
    images: ["/og?kind=painpoint&title=Industry%20Rankings&subtitle=Cross-industry%20benchmarking"],
  },
};

export const revalidate = 600;

interface IndustryRow {
  industry: string;
  painpoint_count: number;
  avg_score: number;
  top_pain: string;
  top_pain_score: number | null;
}

export default async function IndustryPage() {
  let rows: IndustryRow[] = [];
  try {
    const r = await fetch(`${process.env.NEXT_PUBLIC_SITE_URL || "http://localhost:3000"}/api/industry/ranking?limit=30`, {
      next: { revalidate: 600 },
    });
    if (r.ok) rows = await r.json();
  } catch {}

  const locale = getLocale();
  const t = makeT(locale);

  return (
    <main className="mx-auto max-w-5xl px-6 py-12">
      <header className="mb-10">
        <div className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/60 px-4 py-1.5 text-xs text-slate-300">
          <Building2 className="h-3.5 w-3.5 text-amber-400" />
          Cross-Industry Benchmarking
        </div>
        <h1 className="mt-4 text-3xl font-bold sm:text-4xl">Industry Pain Rankings</h1>
        <p className="mt-3 max-w-2xl text-sm text-slate-400">
          Compare pain point intensity across industries. Higher average scores indicate sectors with more urgent, unsolved problems ripe for disruption.
        </p>
      </header>

      {rows.length === 0 ? (
        <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-10 text-center">
          <TrendingUp className="mx-auto h-8 w-8 text-slate-600" />
          <p className="mt-3 text-slate-400">No industry data yet. Rankings appear after the pipeline processes painpoints with industry tags.</p>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs uppercase tracking-wider text-slate-500">
                <th className="py-3 pr-4">#</th>
                <th className="py-3 pr-4">Industry</th>
                <th className="py-3 pr-4 text-right">Pain Points</th>
                <th className="py-3 pr-4 text-right">Avg Score</th>
                <th className="py-3">Top Pain Point</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, i) => (
                <tr
                  key={row.industry}
                  className="border-b border-slate-800/50 transition hover:bg-slate-900/30"
                >
                  <td className="py-3 pr-4 font-mono text-xs text-slate-600">{i + 1}</td>
                  <td className="py-3 pr-4">
                    <Link
                      href={`/industry/${encodeURIComponent(row.industry)}`}
                      className="font-medium text-white hover:text-brand transition"
                    >
                      {row.industry}
                    </Link>
                  </td>
                  <td className="py-3 pr-4 text-right tabular-nums text-slate-400">
                    {row.painpoint_count}
                  </td>
                  <td className="py-3 pr-4 text-right">
                    <span
                      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium tabular-nums ${
                        row.avg_score >= 80
                          ? "bg-red-500/15 text-red-400"
                          : row.avg_score >= 65
                            ? "bg-amber-500/15 text-amber-400"
                            : "bg-emerald-500/15 text-emerald-400"
                      }`}
                    >
                      {row.avg_score.toFixed(1)}
                    </span>
                  </td>
                  <td className="py-3">
                    <div className="flex items-center gap-2">
                      <span className="line-clamp-1 text-slate-300">{row.top_pain}</span>
                      {row.top_pain_score !== null && (
                        <span className="shrink-0 rounded bg-brand/15 px-1.5 py-0.5 text-xs text-brand tabular-nums">
                          {row.top_pain_score.toFixed(0)}
                        </span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-10 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <div className="flex items-start gap-3">
          <Zap className="mt-0.5 h-5 w-5 text-amber-400" />
          <div>
            <h3 className="font-medium text-white">Want deeper insights?</h3>
            <p className="mt-1 text-sm text-slate-400">
              Upgrade to Pro to unlock full industry reports with evidence chains, competitor analysis, and MVP scoping for each pain point.
            </p>
            <Link
              href="/pricing"
              className="mt-3 inline-flex items-center gap-1 text-sm font-medium text-brand hover:underline"
            >
              View Plans <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
