import Link from "next/link";
import { headers } from "next/headers";
import { redirect } from "next/navigation";
import { CheckCircle2, KeyRound, Lock } from "lucide-react";

import {
  serverFetch,
  type MeResponse,
  type SubscriptionResponse,
} from "@/lib/api";
import { getLocale, makeT, t } from "@/lib/i18n";
import { RedeemForm } from "./redeem-form";
import { LogoutButton } from "./logout-button";
import { PortalButton } from "./portal-button";
import { ReferralCard } from "./referral-card";

export const dynamic = "force-dynamic";

export default async function AccountPage({
  searchParams,
}: {
  searchParams?: { paid?: string; session?: string };
}) {
  const cookieHeader = headers().get("cookie");
  const me = await serverFetch<MeResponse>("/api/auth/me", cookieHeader);
  if (!me) {
    redirect("/login?next=/account");
  }
  const subs = await serverFetch<SubscriptionResponse>(
    "/api/billing/subscription",
    cookieHeader,
  );

  const ent = me.entitlement;
  const items = subs?.items ?? [];
  const hasStripeSub = items.some((i) => i.provider === "stripe");
  const justPaid = searchParams?.paid === "1";

  const locale = getLocale();
  const tx = makeT(locale);

  // Pre-build dicts for client islands.
  const redeemDict = {
    "redeem.placeholder": t("redeem.placeholder", locale),
    "redeem.activate": t("redeem.activate", locale),
    "redeem.activating": t("redeem.activating", locale),
    "redeem.successFmt": t("redeem.successFmt", locale),
    "redeem.successPerm": t("redeem.successPerm", locale),
    "account.redeem.error": t("account.redeem.error", locale),
  };
  const logoutDict = {
    "logout.signingOut": t("logout.signingOut", locale),
    "logout.button": t("logout.button", locale),
  };
  const portalDict = {
    "portal.button": t("portal.button", locale),
  };
  const referralDict = {
    "account.referral.title": t("account.referral.title", locale),
    "account.referral.body": t("account.referral.body", locale),
    "account.referral.copied": t("account.referral.copied", locale),
    "common.copy": t("common.copy", locale),
  };

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-semibold">{tx("account.heading")}</h1>
          <p className="mt-1 text-sm text-slate-400">
            {tx("account.emailPrefix")}{" "}
            <span className="text-slate-200">{me.email}</span>
            {me.is_admin && (
              <span className="ml-2 rounded bg-amber-500/15 px-2 py-0.5 text-xs text-amber-300">
                {tx("account.adminBadge")}
              </span>
            )}
          </p>
        </div>
        <LogoutButton dict={logoutDict} />
      </div>

      {justPaid && (
        <div className="mt-6 rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-4 text-sm text-emerald-200">
          <CheckCircle2 className="mr-2 inline h-4 w-4" />
          {tx("account.justPaid")}
        </div>
      )}

      <section className="mt-10 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold">{tx("account.entitlement.title")}</h2>
        <ul className="mt-4 space-y-2 text-sm">
          <EntRow label={tx("account.entitlement.weekly")} on={ent.can_read_weekly_full} />
          <EntRow label={tx("account.entitlement.briefs")} on={ent.can_read_any_brief} />
          <li className="flex items-start gap-2 text-slate-300">
            {ent.unlocked_brief_ids.length > 0 ? (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
            ) : (
              <Lock className="mt-0.5 h-4 w-4 shrink-0 text-slate-600" />
            )}
            <span>
              {tx("account.entitlement.unlocks")}{" "}
              {ent.unlocked_brief_ids.length > 0 ? (
                <span className="text-slate-200">
                  #{ent.unlocked_brief_ids.join(", #")}
                </span>
              ) : (
                <span className="text-slate-500">{tx("account.entitlement.none")}</span>
              )}
            </span>
          </li>
        </ul>
      </section>

      <section className="mt-8 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="text-lg font-semibold">{tx("account.subs.title")}</h2>
        {items.length === 0 ? (
          <p className="mt-4 text-sm text-slate-400">{tx("account.subs.empty")}</p>
        ) : (
          <table className="mt-4 w-full text-left text-sm">
            <thead className="text-slate-500">
              <tr>
                <th className="py-2 font-normal">{tx("account.subs.col.plan")}</th>
                <th className="py-2 font-normal">{tx("account.subs.col.status")}</th>
                <th className="py-2 font-normal">{tx("account.subs.col.source")}</th>
                <th className="py-2 font-normal">{tx("account.subs.col.expires")}</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              {items.map((s) => (
                <tr key={s.id} className="text-slate-200">
                  <td className="py-2">{s.plan}</td>
                  <td className="py-2">
                    <span
                      className={
                        s.status === "active"
                          ? "rounded bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300"
                          : "rounded bg-slate-700/40 px-2 py-0.5 text-xs text-slate-300"
                      }
                    >
                      {s.status}
                    </span>
                  </td>
                  <td className="py-2 text-slate-400">{s.provider}</td>
                  <td className="py-2 text-slate-400">
                    {s.expires_at
                      ? new Date(s.expires_at).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
        <PortalButton hasStripeSub={hasStripeSub} dict={portalDict} />
      </section>

      {me.referral_url && (
        <ReferralCard url={me.referral_url} dict={referralDict} />
      )}

      <section className="mt-8 rounded-xl border border-slate-800 bg-slate-900/40 p-6">
        <h2 className="flex items-center gap-2 text-lg font-semibold">
          <KeyRound className="h-5 w-5 text-brand" /> {tx("account.redeem.heading")}
        </h2>
        <p className="mt-2 text-sm text-slate-400">{tx("account.redeem.intro")}</p>
        <RedeemForm dict={redeemDict} />
      </section>

      <p className="mt-10 text-center text-xs text-slate-500">
        {tx("account.help")}{" "}
        <Link href="/pricing" className="text-brand hover:underline">
          {tx("account.help.link")}
        </Link>
      </p>
    </main>
  );
}

function EntRow({ label, on }: { label: string; on: boolean }) {
  return (
    <li className="flex items-start gap-2 text-slate-300">
      {on ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
      ) : (
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-slate-600" />
      )}
      <span className={on ? "" : "text-slate-500"}>{label}</span>
    </li>
  );
}
