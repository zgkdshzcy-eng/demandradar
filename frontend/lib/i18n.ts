/**
 * Tiny zero-dep i18n.
 *
 * Why not next-intl: that library wants a routing rewrite (`/[locale]/...`),
 * which is heavy for a marketing site that already has lots of public URLs in
 * sitemaps + indexed by Google. Instead we:
 *
 *  - keep all URLs as-is
 *  - read the locale from the `dr_lang` cookie (server) or `document.cookie`
 *    (client), defaulting to `zh`
 *  - expose a small `t(key, locale)` lookup against bundled JSON
 *  - ship a `<LocaleSwitcher>` button that flips the cookie and reloads
 *
 * This means we get bilingual chrome (nav + landing + insights labels) without
 * disturbing SEO. SSR pages call `getLocale()` at the top.
 */
import { cookies, headers } from "next/headers";

import en from "@/messages/en.json";
import zh from "@/messages/zh.json";

export type Locale = "zh" | "en";

export const LOCALES: Locale[] = ["zh", "en"];
export const DEFAULT_LOCALE: Locale = "en";
export const COOKIE_NAME = "dr_lang";

const BUNDLES: Record<Locale, Record<string, string>> = {
  zh: zh as Record<string, string>,
  en: en as Record<string, string>,
};

export function isLocale(s: unknown): s is Locale {
  return s === "zh" || s === "en";
}

/** Server-only: read locale from cookie, fallback to Accept-Language, then default. */
export function getLocale(): Locale {
  try {
    const c = cookies().get(COOKIE_NAME)?.value;
    if (isLocale(c)) return c;
  } catch {
    // not in a request scope
  }
  try {
    const accept = headers().get("accept-language") || "";
    // Bias to zh only if Accept-Language explicitly prefers Chinese.
    if (/^zh\b/i.test(accept)) return "zh";
  } catch {
    // no headers available
  }
  return DEFAULT_LOCALE;
}

/** Lookup a translation key, with `{var}` interpolation. Falls back to the
 *  default locale, then to the key itself, so missing strings never crash. */
export function t(
  key: string,
  locale: Locale = DEFAULT_LOCALE,
  vars?: Record<string, string | number>,
): string {
  const bundle = BUNDLES[locale] || BUNDLES[DEFAULT_LOCALE];
  let s = bundle[key] ?? BUNDLES[DEFAULT_LOCALE][key] ?? key;
  if (vars) {
    for (const [k, v] of Object.entries(vars)) {
      s = s.replace(new RegExp(`\\{${k}\\}`, "g"), String(v));
    }
  }
  return s;
}

/** Convenience: bind the locale once, return a `(key, vars?) => string`. */
export function makeT(locale: Locale) {
  return (key: string, vars?: Record<string, string | number>) =>
    t(key, locale, vars);
}
