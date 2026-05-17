/**
 * Client-side i18n helper.
 *
 * Server components import { getLocale, t } from "@/lib/i18n". Client
 * components are leaves of the SSR tree, so they receive the resolved locale
 * + a small dictionary of needed keys via props from their server parent.
 *
 * That keeps the client bundle tiny (no JSON of all translations shipped) and
 * avoids the runtime cost of reading document.cookie on every render.
 */
"use client";

export type ClientDict = Record<string, string>;

const COOKIE_NAME = "dr_lang";

/**
 * Read the locale cookie set by the server (`getLocale()` in lib/i18n.ts).
 * Returns "en" | "zh" | undefined. Safe to call on the server (returns
 * undefined there since `document` is missing).
 */
export function readLocaleCookie(): string | undefined {
  if (typeof document === "undefined") return undefined;
  const m = document.cookie.match(
    new RegExp(`(?:^|; )${COOKIE_NAME}=([^;]*)`),
  );
  if (!m) return undefined;
  const v = decodeURIComponent(m[1]).toLowerCase();
  return v === "en" || v === "zh" ? v : undefined;
}

/** Lookup with `{var}` interpolation. Falls back to the key itself. */
export function ct(
  dict: ClientDict,
  key: string,
  vars?: Record<string, string | number>,
): string {
  let s = dict[key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}
