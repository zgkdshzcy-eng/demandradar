"use client";

import { useEffect } from "react";

const COOKIE_NAME = "dr_ref";
const TTL_DAYS = 30;

/**
 * Captures `?ref=XXXX` on first landing and stores it in a long-lived cookie
 * so that subsequent /login flows can attach the referral code regardless of
 * how the visitor navigates the site.
 *
 * Mounted in the root layout. Renders nothing.
 */
export function ReferralCookie() {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const url = new URL(window.location.href);
    const ref = url.searchParams.get("ref");
    if (!ref) return;
    // Sanity bound — referral_code is 8 chars upper+digits in the backend.
    const sanitized = ref.replace(/[^A-Z0-9]/gi, "").slice(0, 16).toUpperCase();
    if (!sanitized) return;
    const expires = new Date(Date.now() + TTL_DAYS * 86400 * 1000).toUTCString();
    document.cookie = `${COOKIE_NAME}=${sanitized}; path=/; expires=${expires}; SameSite=Lax`;
  }, []);
  return null;
}

/** Helper for client components that need the cookie to attach to fetches. */
export function readReferralCookie(): string | null {
  if (typeof document === "undefined") return null;
  const m = document.cookie.match(new RegExp("(?:^|; )" + COOKIE_NAME + "=([^;]+)"));
  return m ? decodeURIComponent(m[1]) : null;
}
