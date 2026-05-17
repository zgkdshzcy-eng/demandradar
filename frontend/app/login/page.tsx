import { getLocale, t } from "@/lib/i18n";

import { LoginForm } from "./login-form";

const KEYS = [
  "login.title",
  "login.subtitle",
  "login.button",
  "login.sending",
  "login.placeholder",
  "login.consent",
  "login.terms",
  "login.sentToPrefix",
  "login.smtpDisabledNote",
  "login.linkValidNote",
  "login.devModeTitle",
  "login.devModeBody",
  "login.connectError",
  "common.email",
] as const;

export const metadata = {
  title: "Sign in",
  alternates: { canonical: "/login" },
};

export default function LoginPage() {
  const locale = getLocale();
  const dict: Record<string, string> = {};
  for (const k of KEYS) dict[k] = t(k, locale);
  return <LoginForm dict={dict} />;
}
