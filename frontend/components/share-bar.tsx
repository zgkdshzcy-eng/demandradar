"use client";

import { useState } from "react";
import { Check, Copy, Link2 } from "lucide-react";

import { ct, type ClientDict } from "@/lib/i18n-client";

interface Props {
  url: string;
  title: string;
  summary?: string;
  dict: ClientDict;
}

/**
 * Bilingual share bar: X (Twitter), LinkedIn, Hacker News for the
 * international audience plus Weibo + WeChat (copy-link with toast) for the
 * Chinese audience. WeChat does not support direct share URLs from the
 * desktop web — copying the canonical URL is the standard workaround.
 */
export function ShareBar({ url, title, summary = "", dict }: Props) {
  const [copied, setCopied] = useState(false);

  const enc = encodeURIComponent;
  const tweet = `https://twitter.com/intent/tweet?text=${enc(title)}&url=${enc(url)}`;
  const linkedin = `https://www.linkedin.com/sharing/share-offsite/?url=${enc(url)}`;
  const hn = `https://news.ycombinator.com/submitlink?u=${enc(url)}&t=${enc(title)}`;
  const weibo = `https://service.weibo.com/share/share.php?url=${enc(url)}&title=${enc(title)}&pic=&searchPic=false`;

  async function copy() {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // ignore
    }
  }

  const Btn = ({
    href,
    label,
    children,
  }: {
    href: string;
    label: string;
    children: React.ReactNode;
  }) => (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={label}
      title={label}
      className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900/40 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-white"
    >
      {children}
    </a>
  );

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-slate-500">
        {ct(dict, "share.label") || "Share:"}
      </span>
      <Btn href={tweet} label="X / Twitter">
        X / Twitter
      </Btn>
      <Btn href={linkedin} label="LinkedIn">
        LinkedIn
      </Btn>
      <Btn href={hn} label="Hacker News">
        Hacker News
      </Btn>
      <Btn href={weibo} label="Weibo">
        微博
      </Btn>
      <button
        type="button"
        onClick={copy}
        aria-label={ct(dict, "share.copy") || "Copy link"}
        className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900/40 px-3 py-1.5 text-xs text-slate-300 hover:border-slate-500 hover:text-white"
      >
        {copied ? (
          <>
            <Check className="h-3.5 w-3.5 text-emerald-400" />
            {ct(dict, "share.copied") || "Copied"}
          </>
        ) : (
          <>
            <Link2 className="h-3.5 w-3.5" />
            {ct(dict, "share.copy") || "Copy link"}
          </>
        )}
      </button>
      {summary ? <span className="sr-only">{summary}</span> : null}
    </div>
  );
}

/**
 * Equivalent of <ShareBar> but written as a server component to drop into a
 * server page. We can't share state, so just render the static anchors. For
 * pages that want the copy-to-clipboard button, import <ShareBar> directly.
 */
export function ShareBarStatic({
  url,
  title,
}: {
  url: string;
  title: string;
}) {
  const enc = encodeURIComponent;
  const items: Array<[string, string]> = [
    ["X", `https://twitter.com/intent/tweet?text=${enc(title)}&url=${enc(url)}`],
    [
      "LinkedIn",
      `https://www.linkedin.com/sharing/share-offsite/?url=${enc(url)}`,
    ],
    [
      "Hacker News",
      `https://news.ycombinator.com/submitlink?u=${enc(url)}&t=${enc(title)}`,
    ],
    [
      "微博",
      `https://service.weibo.com/share/share.php?url=${enc(url)}&title=${enc(title)}`,
    ],
  ];
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs text-slate-400">
      {items.map(([label, href]) => (
        <a
          key={label}
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900/40 px-3 py-1.5 hover:border-slate-500 hover:text-white"
        >
          {label}
        </a>
      ))}
    </div>
  );
}
