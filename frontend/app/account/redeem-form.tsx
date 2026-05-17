"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowRight, CheckCircle2, AlertTriangle } from "lucide-react";

import { api } from "@/lib/api";
import { ct, type ClientDict } from "@/lib/i18n-client";

interface Props {
  dict: ClientDict;
}

export function RedeemForm({ dict }: Props) {
  const router = useRouter();
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    const r = await api.redeem(code.trim());
    setLoading(false);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    setCode("");
    if (r.data.expires_at) {
      const date = new Date(r.data.expires_at).toLocaleDateString();
      setSuccess(ct(dict, "redeem.successFmt", { plan: r.data.plan, date }));
    } else {
      setSuccess(ct(dict, "redeem.successPerm", { plan: r.data.plan }));
    }
    router.refresh();
  }

  return (
    <form onSubmit={onSubmit} className="mt-4 space-y-3">
      <textarea
        value={code}
        onChange={(e) => setCode(e.target.value)}
        rows={3}
        placeholder={ct(dict, "redeem.placeholder")}
        className="w-full rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 font-mono text-xs text-slate-200 outline-none focus:border-brand"
      />
      <button
        type="submit"
        disabled={loading || code.length < 10}
        className="inline-flex items-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
      >
        {loading ? ct(dict, "redeem.activating") : ct(dict, "redeem.activate")}
        <ArrowRight className="h-4 w-4" />
      </button>
      {success && (
        <p className="flex items-start gap-2 text-sm text-emerald-300">
          <CheckCircle2 className="mt-0.5 h-4 w-4" />
          {success}
        </p>
      )}
      {error && (
        <p className="flex items-start gap-2 text-sm text-red-300">
          <AlertTriangle className="mt-0.5 h-4 w-4" />
          {error}
        </p>
      )}
    </form>
  );
}
