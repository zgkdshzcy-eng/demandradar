"use client";

import { useState } from "react";
import { Copy, Check, Gift } from "lucide-react";

import { ct, type ClientDict } from "@/lib/i18n-client";

interface Props {
  url: string;
  dict: ClientDict;
}

export function ReferralCard({ url, dict }: Props) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // no-op fallback for MVP
    }
  }

  return (
    <section className="mt-8 rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-6">
      <h2 className="flex items-center gap-2 text-lg font-semibold">
        <Gift className="h-5 w-5 text-emerald-400" /> {ct(dict, "account.referral.title")}
      </h2>
      <p className="mt-2 text-sm text-slate-400">{ct(dict, "account.referral.body")}</p>
      <div className="mt-4 flex items-center gap-2">
        <code className="flex-1 truncate rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-xs text-slate-200">
          {url}
        </code>
        <button
          onClick={copy}
          className="inline-flex items-center gap-1 rounded-md border border-slate-700 px-3 py-2 text-sm hover:border-slate-500"
        >
          {copied ? (
            <>
              <Check className="h-4 w-4 text-emerald-400" />{" "}
              {ct(dict, "account.referral.copied")}
            </>
          ) : (
            <>
              <Copy className="h-4 w-4" /> {ct(dict, "common.copy")}
            </>
          )}
        </button>
      </div>
    </section>
  );
}
