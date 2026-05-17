"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { api } from "@/lib/api";

interface Props {
  plan: "weekly_pro" | "studio" | "brief_oneoff";
  briefId?: number;
  className?: string;
  children: React.ReactNode;
}

/**
 * Wraps any element in a "buy" button that:
 * 1. Hits POST /api/billing/checkout
 * 2. Redirects the browser to the returned Stripe URL
 * 3. If Stripe is disabled (mode=redeem_only), shows a friendly message
 * 4. If the user is not logged in (401), bounces them to /login?next=...
 */
export function CheckoutButton({ plan, briefId, className, children }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onClick() {
    setLoading(true);
    setError(null);
    const me = await api.me();
    if (!me) {
      router.push(`/login?next=${encodeURIComponent("/pricing")}`);
      return;
    }
    const r = await api.checkout({ plan, brief_id: briefId });
    setLoading(false);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    if (r.data.mode === "redeem_only") {
      setError(r.data.message);
      return;
    }
    if (r.data.url) {
      window.location.href = r.data.url;
    } else {
      setError("Stripe returned no URL.");
    }
  }

  return (
    <div className="inline-flex flex-col">
      <button
        onClick={onClick}
        disabled={loading}
        className={
          className ??
          "inline-flex items-center justify-center gap-1.5 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
        }
      >
        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
        {children}
      </button>
      {error && (
        <span className="mt-1 max-w-xs text-xs text-amber-300">{error}</span>
      )}
    </div>
  );
}
