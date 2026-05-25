"use client";

import { useEffect, useState } from "react";
import { Gift, Loader2, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";

export function ShareClaimBanner() {
  const [shareToken, setShareToken] = useState<string | null>(null);
  const [briefId, setBriefId] = useState<number | null>(null);
  const [claiming, setClaiming] = useState(false);
  const [claimed, setClaimed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const share = url.searchParams.get("share");
    const bid = url.searchParams.get("bid");
    if (share) {
      setShareToken(share);
      if (bid) setBriefId(parseInt(bid, 10));
      const expires = new Date(Date.now() + 7 * 86400 * 1000).toUTCString();
      document.cookie = "dr_share=" + share + "; path=/; expires=" + expires + "; SameSite=Lax";
      if (bid) {
        document.cookie = "dr_share_bid=" + bid + "; path=/; expires=" + expires + "; SameSite=Lax";
      }
      url.searchParams.delete("share");
      url.searchParams.delete("bid");
      window.history.replaceState({}, "", url.toString());
    } else {
      const m = document.cookie.match(/(?:^|; )dr_share=([^;]+)/);
      if (m) setShareToken(decodeURIComponent(m[1]));
      const bm = document.cookie.match(/(?:^|; )dr_share_bid=([^;]+)/);
      if (bm) setBriefId(parseInt(decodeURIComponent(bm[1]), 10));
    }
  }, []);

  async function handleClaim() {
    if (!shareToken) return;
    setClaiming(true);
    setError(null);
    const r = await api.claimShareUnlock(shareToken);
    setClaiming(false);
    if (r.ok) {
      setClaimed(true);
      document.cookie = "dr_share=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
      document.cookie = "dr_share_bid=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT";
    } else {
      setError(r.error);
    }
  }

  if (dismissed || !shareToken) return null;

  return (
    <div className="mx-auto max-w-3xl px-6 pt-6">
      <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/10 p-5">
        <div className="flex items-start gap-3">
          {claimed ? (
            <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
          ) : (
            <Gift className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400" />
          )}
          <div className="flex-1 text-sm">
            {claimed ? (
              <>
                <p className="font-medium text-emerald-200">解锁成功！</p>
                <p className="mt-1 text-emerald-300/70">
                  你现在可以查看 Brief #{briefId} 的完整内容。
                </p>
              </>
            ) : (
              <>
                <p className="font-medium text-emerald-200">
                  你通过好友分享链接访问，可以免费解锁 1 个 Brief！
                </p>
                <p className="mt-1 text-emerald-300/70">
                  点击下方按钮领取你的免费解锁。
                </p>
                <div className="mt-3 flex items-center gap-3">
                  <button
                    onClick={handleClaim}
                    disabled={claiming}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-600 disabled:opacity-60"
                  >
                    {claiming && <Loader2 className="h-4 w-4 animate-spin" />}
                    {claiming ? "领取中..." : "领取免费解锁"}
                  </button>
                  <button
                    onClick={() => setDismissed(true)}
                    className="text-xs text-slate-400 hover:text-slate-200"
                  >
                    暂不领取
                  </button>
                </div>
                {error && (
                  <p className="mt-2 text-xs text-red-400">{error}</p>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
