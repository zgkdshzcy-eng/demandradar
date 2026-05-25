"use client";

import { useState } from "react";
import { Share2, Twitter, Link2, Check, Loader2 } from "lucide-react";
import { api } from "@/lib/api";

interface Props {
  briefId?: number;
  painPointId?: number;
  className?: string;
}

export function ShareUnlockButton({ briefId, painPointId, className = "" }: Props) {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{
    share_url: string;
    twitter_url: string | null;
    message: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);
  const [showModal, setShowModal] = useState(false);

  async function handleShare(platform?: string) {
    setLoading(true);
    const r = await api.createShareUnlock({
      brief_id: briefId,
      pain_point_id: painPointId,
      platform,
    });
    setLoading(false);
    if (r) {
      setResult({ share_url: r.share_url, twitter_url: r.twitter_url, message: r.message });
      setShowModal(true);
    }
  }

  function copyLink() {
    if (!result) return;
    navigator.clipboard.writeText(result.share_url).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  return (
    <>
      <button
        onClick={() => handleShare()}
        disabled={loading}
        className={`inline-flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-4 py-2 text-sm font-medium text-emerald-300 transition hover:bg-emerald-500/20 disabled:opacity-60 ${className}`}
      >
        {loading ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : (
          <Share2 className="h-4 w-4" />
        )}
        分享解锁免费查看
      </button>

      {showModal && result && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-xl">
            <h3 className="text-lg font-semibold text-white">分享解锁</h3>
            <p className="mt-2 text-sm text-slate-400">{result.message}</p>

            <div className="mt-5 space-y-3">
              {result.twitter_url && (
                <a
                  href={result.twitter_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex w-full items-center justify-center gap-2 rounded-lg bg-[#1d9bf0] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#1a8cd8]"
                  onClick={() => setShowModal(false)}
                >
                  <Twitter className="h-4 w-4" />
                  分享到 Twitter/X
                </a>
              )}

              <button
                onClick={copyLink}
                className="flex w-full items-center justify-center gap-2 rounded-lg border border-slate-600 px-4 py-2.5 text-sm font-medium text-white hover:border-slate-400"
              >
                {copied ? (
                  <>
                    <Check className="h-4 w-4 text-emerald-400" />
                    已复制链接
                  </>
                ) : (
                  <>
                    <Link2 className="h-4 w-4" />
                    复制分享链接
                  </>
                )}
              </button>
            </div>

            <button
              onClick={() => setShowModal(false)}
              className="mt-4 w-full text-center text-xs text-slate-500 hover:text-slate-300"
            >
              关闭
            </button>
          </div>
        </div>
      )}
    </>
  );
}
