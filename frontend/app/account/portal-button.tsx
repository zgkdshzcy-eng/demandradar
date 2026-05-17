"use client";

import { useState } from "react";
import { CreditCard, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import { ct, type ClientDict } from "@/lib/i18n-client";

interface Props {
  hasStripeSub: boolean;
  dict: ClientDict;
}

export function PortalButton({ hasStripeSub, dict }: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!hasStripeSub) return null;

  async function onClick() {
    setLoading(true);
    setError(null);
    const r = await api.openPortal();
    if (!r.ok) {
      setError(r.error);
      setLoading(false);
      return;
    }
    window.location.href = r.url;
  }

  return (
    <div className="mt-4">
      <button
        onClick={onClick}
        disabled={loading}
        className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-200 hover:border-slate-500 disabled:opacity-60"
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <CreditCard className="h-4 w-4" />
        )}
        {ct(dict, "portal.button")}
      </button>
      {error && <p className="mt-1 text-xs text-amber-300">{error}</p>}
    </div>
  );
}
