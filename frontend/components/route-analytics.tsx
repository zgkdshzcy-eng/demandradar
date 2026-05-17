"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect } from "react";

interface Props {
  gaId: string;
  baiduId: string;
}

declare global {
  interface Window {
    gtag?: (...args: unknown[]) => void;
    _hmt?: Array<unknown[]>;
  }
}

/**
 * Fire a pageview to GA and Baidu Tongji whenever the App Router pathname
 * changes. Both libraries default to a single SPA load otherwise.
 */
export function RouteAnalytics({ gaId, baiduId }: Props) {
  const pathname = usePathname();
  const search = useSearchParams();

  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = pathname + (search?.toString() ? `?${search.toString()}` : "");
    if (gaId && typeof window.gtag === "function") {
      window.gtag("event", "page_view", {
        page_path: url,
        page_location: window.location.href,
        page_title: document.title,
      });
    }
    if (baiduId && Array.isArray(window._hmt)) {
      window._hmt.push(["_trackPageview", url]);
    }
  }, [pathname, search, gaId, baiduId]);

  return null;
}
