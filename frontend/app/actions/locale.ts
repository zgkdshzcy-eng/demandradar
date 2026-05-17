"use server";

import { cookies } from "next/headers";

import { COOKIE_NAME, isLocale } from "@/lib/i18n";

/**
 * Server action: write the `dr_lang` cookie. Called from <LocaleSwitcher>.
 *
 * 1-year persistence, lax sameSite — the cookie is non-sensitive and read on
 * every SSR pass.
 */
export async function setLocaleAction(formData: FormData): Promise<void> {
  const next = formData.get("locale");
  if (!isLocale(next)) return;
  cookies().set({
    name: COOKIE_NAME,
    value: next,
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
    httpOnly: false,
  });
}
