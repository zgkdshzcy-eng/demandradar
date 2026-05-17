import { getLocale, t } from "@/lib/i18n";

import { WaitlistForm } from "./waitlist-form";

const KEYS = [
  "waitlist.placeholder",
  "waitlist.button",
  "waitlist.joining",
  "waitlist.success",
  "waitlist.error",
] as const;

/**
 * Server wrapper that builds a tiny dict of waitlist strings for the client
 * form. Pages that already have access to `getLocale()` can call this
 * instead of using <WaitlistForm /> directly so they get localised copy.
 */
export function WaitlistFormI18n() {
  const locale = getLocale();
  const dict: Record<string, string> = {};
  for (const k of KEYS) {
    dict[k] = t(k, locale);
  }
  return <WaitlistForm dict={dict} />;
}
