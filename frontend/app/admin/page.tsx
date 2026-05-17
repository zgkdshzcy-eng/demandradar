import { headers } from "next/headers";
import { redirect } from "next/navigation";
import {
  Activity,
  Coins,
  Mail,
  Megaphone,
  Send,
  ShieldCheck,
} from "lucide-react";

import { serverFetch, type AdminStats, type MeResponse } from "@/lib/api";

interface SocialPostRow {
  id: number;
  platform: string;
  status: string;
  kind: string;
  title: string | null;
  body: string;
  url: string | null;
  external_id: string | null;
  error: string | null;
  posted_at: string | null;
  created_at: string;
}

interface DispatchRow {
  id: number;
  campaign: string;
  email: string;
  status: string;
  attempts: number;
  sent_at: string | null;
  error: string | null;
}

interface DispatchesResponse {
  campaign: string | null;
  rows: DispatchRow[];
  summary: Record<string, number>;
}

interface LLMProviderRow {
  provider: string;
  model: string;
  calls: number;
  success: number;
  failures: number;
  tokens: number;
  cost_cny: number;
}

interface LLMBudgetResponse {
  spent_cny: number;
  limit_cny: number;
  remaining_cny: number;
  used_pct: number;
  over: boolean;
  by_provider: LLMProviderRow[];
  top_purposes: Array<{ purpose: string; calls: number; cost_cny: number }>;
}

export const dynamic = "force-dynamic";

export const metadata = {
  title: "Admin",
  robots: { index: false, follow: false },
};

export default async function AdminPage() {
  const cookieHeader = headers().get("cookie");
  const me = await serverFetch<MeResponse>("/api/auth/me", cookieHeader);
  if (!me) redirect("/login?next=/admin");
  if (!me.is_admin) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-2xl font-semibold">Forbidden</h1>
        <p className="mt-2 text-sm text-slate-400">
          This page is only visible to administrators.
        </p>
      </main>
    );
  }

  const [stats, phPosts, xPosts, budget, dispatches] = await Promise.all([
    serverFetch<AdminStats>("/api/admin/stats", cookieHeader),
    serverFetch<SocialPostRow[]>(
      "/api/admin/social-posts?platform=producthunt&limit=10",
      cookieHeader,
    ),
    serverFetch<SocialPostRow[]>(
      "/api/admin/social-posts?platform=x&limit=10",
      cookieHeader,
    ),
    serverFetch<LLMBudgetResponse>("/api/admin/llm-budget", cookieHeader),
    serverFetch<DispatchesResponse>(
      "/api/admin/dispatches?limit=30",
      cookieHeader,
    ),
  ]);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-8 flex items-center gap-2">
        <ShieldCheck className="h-6 w-6 text-emerald-400" />
        <h1 className="text-3xl font-semibold">Operations dashboard</h1>
      </header>

      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {(stats?.cards ?? []).map((c) => (
          <div
            key={c.label}
            className="rounded-xl border border-slate-800 bg-slate-900/40 p-5"
          >
            <div className="text-xs text-slate-500">{c.label}</div>
            <div className="mt-2 text-2xl font-bold tabular-nums text-white">
              {typeof c.value === "number" && Number.isFinite(c.value)
                ? c.value.toLocaleString()
                : c.value}
            </div>
            {c.note && (
              <div className="mt-1 text-xs text-slate-500">{c.note}</div>
            )}
          </div>
        ))}
      </section>

      {budget && (
        <section className="mt-10">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Coins className="h-5 w-5 text-amber-400" /> LLM budget
          </h2>
          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="text-xs text-slate-500">Spent today</div>
              <div className="mt-1 text-xl font-bold tabular-nums text-white">
                ¥{budget.spent_cny.toFixed(2)}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="text-xs text-slate-500">Daily cap</div>
              <div className="mt-1 text-xl font-bold tabular-nums text-white">
                ¥{budget.limit_cny.toFixed(0)}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="text-xs text-slate-500">Remaining</div>
              <div className="mt-1 text-xl font-bold tabular-nums text-white">
                ¥{budget.remaining_cny.toFixed(2)}
              </div>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-4">
              <div className="text-xs text-slate-500">Used</div>
              <div className="mt-1 text-xl font-bold tabular-nums text-white">
                {budget.used_pct}%
              </div>
              {budget.over && (
                <div className="mt-1 text-xs font-medium text-rose-400">
                  Over budget
                </div>
              )}
            </div>
          </div>

          {budget.by_provider.length > 0 && (
            <div className="mt-4 overflow-hidden rounded-xl border border-slate-800">
              <table className="w-full text-sm">
                <thead className="bg-slate-900/60 text-left text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-normal">Provider</th>
                    <th className="px-4 py-3 font-normal">Model</th>
                    <th className="px-4 py-3 font-normal text-right">Calls</th>
                    <th className="px-4 py-3 font-normal text-right">OK</th>
                    <th className="px-4 py-3 font-normal text-right">Fail</th>
                    <th className="px-4 py-3 font-normal text-right">Tokens</th>
                    <th className="px-4 py-3 font-normal text-right">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {budget.by_provider.map((r, i) => (
                    <tr key={i} className="text-slate-200">
                      <td className="px-4 py-2 font-mono text-xs">{r.provider}</td>
                      <td className="px-4 py-2 font-mono text-xs text-slate-400">
                        {r.model}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">{r.calls}</td>
                      <td className="px-4 py-2 text-right tabular-nums text-emerald-400">
                        {r.success}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums text-rose-400">
                        {r.failures}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        {r.tokens.toLocaleString()}
                      </td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        ¥{r.cost_cny.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {budget.top_purposes.length > 0 && (
            <div className="mt-4 overflow-hidden rounded-xl border border-slate-800">
              <table className="w-full text-sm">
                <thead className="bg-slate-900/60 text-left text-xs uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-4 py-3 font-normal">Purpose</th>
                    <th className="px-4 py-3 font-normal text-right">Calls</th>
                    <th className="px-4 py-3 font-normal text-right">Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800">
                  {budget.top_purposes.map((p, i) => (
                    <tr key={i} className="text-slate-200">
                      <td className="px-4 py-2 font-mono text-xs">{p.purpose}</td>
                      <td className="px-4 py-2 text-right tabular-nums">{p.calls}</td>
                      <td className="px-4 py-2 text-right tabular-nums">
                        ¥{p.cost_cny.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Subscription distribution</h2>
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-left text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3 font-normal">Plan</th>
                <th className="px-4 py-3 font-normal">Active</th>
                <th className="px-4 py-3 font-normal">Canceled</th>
                <th className="px-4 py-3 font-normal">Refunded</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {(stats?.plans ?? []).map((p) => (
                <tr key={p.plan} className="text-slate-200">
                  <td className="px-4 py-3 font-mono text-xs">{p.plan}</td>
                  <td className="px-4 py-3 tabular-nums">{p.active}</td>
                  <td className="px-4 py-3 tabular-nums text-slate-400">
                    {p.canceled}
                  </td>
                  <td className="px-4 py-3 tabular-nums text-slate-400">
                    {p.refunded}
                  </td>
                </tr>
              ))}
              {!stats?.plans?.length && (
                <tr>
                  <td className="px-4 py-6 text-slate-500" colSpan={4}>
                    No subscriptions yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Activity className="h-5 w-5 text-brand" /> Recent payment events
        </h2>
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-left text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3 font-normal">Time</th>
                <th className="px-4 py-3 font-normal">Type</th>
                <th className="px-4 py-3 font-normal">User</th>
                <th className="px-4 py-3 font-normal">Sub</th>
                <th className="px-4 py-3 font-normal">Stripe event</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {(stats?.recent_events ?? []).map((e) => (
                <tr key={e.id} className="text-slate-300">
                  <td className="px-4 py-2 text-xs text-slate-500">
                    {new Date(e.received_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs">{e.type}</td>
                  <td className="px-4 py-2 tabular-nums">{e.user_id ?? "-"}</td>
                  <td className="px-4 py-2 tabular-nums">
                    {e.subscription_id ?? "-"}
                  </td>
                  <td className="px-4 py-2 font-mono text-xs text-slate-500">
                    {e.event_id}
                  </td>
                </tr>
              ))}
              {!stats?.recent_events?.length && (
                <tr>
                  <td className="px-4 py-6 text-slate-500" colSpan={5}>
                    No events
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-semibold">Top referrers</h2>
        <div className="mt-4 overflow-hidden rounded-xl border border-slate-800">
          <table className="w-full text-sm">
            <thead className="bg-slate-900/60 text-left text-xs uppercase tracking-wider text-slate-500">
              <tr>
                <th className="px-4 py-3 font-normal">User</th>
                <th className="px-4 py-3 font-normal">Code</th>
                <th className="px-4 py-3 font-normal">Grants</th>
                <th className="px-4 py-3 font-normal">Bonus days</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {(stats?.top_referrers ?? []).map((r) => (
                <tr key={r.user_id} className="text-slate-200">
                  <td className="px-4 py-3">{r.email}</td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-400">
                    {r.referral_code ?? "-"}
                  </td>
                  <td className="px-4 py-3 tabular-nums">{r.grants}</td>
                  <td className="px-4 py-3 tabular-nums">{r.total_bonus_days}</td>
                </tr>
              ))}
              {!stats?.top_referrers?.length && (
                <tr>
                  <td className="px-4 py-6 text-slate-500" colSpan={4}>
                    No referrals yet
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>

      {dispatches && (
        <section className="mt-10">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Mail className="h-5 w-5 text-purple-400" /> Newsletter dispatch log
          </h2>
          {Object.keys(dispatches.summary).length > 0 && (
            <div className="mt-2 flex gap-3 text-xs">
              {Object.entries(dispatches.summary).map(([status, n]) => (
                <span
                  key={status}
                  className={`rounded-full px-2.5 py-0.5 font-mono ${
                    status === "sent"
                      ? "bg-emerald-900/40 text-emerald-300"
                      : status === "failed"
                        ? "bg-rose-900/40 text-rose-300"
                        : "bg-slate-800 text-slate-400"
                  }`}
                >
                  {status}: {n}
                </span>
              ))}
            </div>
          )}
          <div className="mt-4 overflow-hidden rounded-xl border border-slate-800">
            <table className="w-full text-sm">
              <thead className="bg-slate-900/60 text-left text-xs uppercase tracking-wider text-slate-500">
                <tr>
                  <th className="px-4 py-3 font-normal">Campaign</th>
                  <th className="px-4 py-3 font-normal">Recipient</th>
                  <th className="px-4 py-3 font-normal">Status</th>
                  <th className="px-4 py-3 font-normal">Attempts</th>
                  <th className="px-4 py-3 font-normal">Sent at</th>
                  <th className="px-4 py-3 font-normal">Error</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800">
                {dispatches.rows.map((r) => (
                  <tr key={r.id} className="text-slate-300">
                    <td className="px-4 py-2 font-mono text-xs">{r.campaign}</td>
                    <td className="px-4 py-2 text-xs">{r.email}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`rounded px-1.5 py-0.5 text-xs font-mono ${
                          r.status === "sent"
                            ? "bg-emerald-900/40 text-emerald-300"
                            : r.status === "failed"
                              ? "bg-rose-900/40 text-rose-300"
                              : "bg-slate-800 text-slate-400"
                        }`}
                      >
                        {r.status}
                      </span>
                    </td>
                    <td className="px-4 py-2 tabular-nums">{r.attempts}</td>
                    <td className="px-4 py-2 text-xs text-slate-500">
                      {r.sent_at ? new Date(r.sent_at).toLocaleString() : "-"}
                    </td>
                    <td className="px-4 py-2 max-w-[200px] truncate text-xs text-rose-400">
                      {r.error ?? "-"}
                    </td>
                  </tr>
                ))}
                {!dispatches.rows.length && (
                  <tr>
                    <td className="px-4 py-6 text-slate-500" colSpan={6}>
                      No dispatches yet
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="mt-10">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Send className="h-5 w-5 text-sky-400" /> X post queue
        </h2>
        <div className="mt-4 grid gap-3">
          {(xPosts ?? []).map((p) => (
            <article
              key={p.id}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
            >
              <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                <span className="rounded bg-slate-800 px-2 py-0.5 font-mono">
                  #{p.id}
                </span>
                <span
                  className={
                    p.status === "posted"
                      ? "text-emerald-400"
                      : p.status === "failed"
                        ? "text-rose-400"
                        : p.status === "manual"
                          ? "text-amber-400"
                          : "text-sky-400"
                  }
                >
                  {p.status}
                </span>
                <span>·</span>
                <span>{p.kind}</span>
                {p.external_id && (
                  <>
                    <span>·</span>
                    <span className="font-mono">{p.external_id}</span>
                  </>
                )}
                <span className="ml-auto">
                  {new Date(p.created_at).toLocaleString()}
                </span>
              </div>
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-200">
                {p.body}
              </pre>
              {p.error && (
                <p className="mt-2 text-xs text-rose-400">⚠ {p.error}</p>
              )}
            </article>
          ))}
          {!xPosts?.length && (
            <p className="text-sm text-slate-500">Queue is empty.</p>
          )}
        </div>
      </section>

      <section className="mt-10">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <Megaphone className="h-5 w-5 text-orange-400" /> ProductHunt candidate copy
        </h2>
        <p className="mt-1 text-xs text-slate-500">
          Copy each block below and paste into the corresponding PH thread.
          Status stays manual — we never auto-publish on PH.
        </p>
        <div className="mt-4 grid gap-3">
          {(phPosts ?? []).map((p) => (
            <article
              key={p.id}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4"
            >
              <div className="mb-2 flex items-center gap-2 text-xs text-slate-500">
                <span className="rounded bg-slate-800 px-2 py-0.5 font-mono">
                  #{p.id}
                </span>
                <span className="font-medium text-slate-300">{p.title}</span>
                {p.url && (
                  <a href={p.url} className="ml-auto text-brand hover:underline">
                    →
                  </a>
                )}
              </div>
              <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-slate-300">
                {p.body}
              </pre>
            </article>
          ))}
          {!phPosts?.length && (
            <p className="text-sm text-slate-500">
              No candidates yet. The next high-score brief will queue one automatically.
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
