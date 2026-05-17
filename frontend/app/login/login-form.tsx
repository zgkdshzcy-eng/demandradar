"use client";

import Link from "next/link";
import { useState } from "react";
import { Mail, ArrowRight, CheckCircle2 } from "lucide-react";

import { api } from "@/lib/api";
import { readReferralCookie } from "@/components/referral-cookie";
import { ct, readLocaleCookie, type ClientDict } from "@/lib/i18n-client";

interface Props {
  dict: ClientDict;
}

export function LoginForm({ dict }: Props) {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [debugLink, setDebugLink] = useState<string | null>(null);
  const [smtpEnabled, setSmtpEnabled] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    const r = await api.requestLink(
      email.trim().toLowerCase(),
      undefined,
      readReferralCookie() || undefined,
      readLocaleCookie(),
    );
    setLoading(false);
    if (!r) {
      setError(ct(dict, "login.connectError"));
      return;
    }
    setSent(true);
    setDebugLink(r.debug_link);
    setSmtpEnabled(r.smtp_enabled);
  }

  return (
    <main className="mx-auto flex min-h-[70vh] max-w-md flex-col justify-center px-6 py-16">
      <h1 className="text-3xl font-semibold">{ct(dict, "login.title")}</h1>
      <p className="mt-2 text-sm text-slate-400">{ct(dict, "login.subtitle")}</p>

      {!sent ? (
        <form onSubmit={onSubmit} className="mt-8 space-y-4">
          <label className="block text-sm">
            <span className="text-slate-300">{ct(dict, "common.email")}</span>
            <div className="mt-1 flex items-center gap-2 rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 focus-within:border-brand">
              <Mail className="h-4 w-4 text-slate-500" />
              <input
                type="email"
                required
                autoFocus
                placeholder={ct(dict, "login.placeholder")}
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full bg-transparent text-sm outline-none placeholder:text-slate-600"
              />
            </div>
          </label>
          <button
            type="submit"
            disabled={loading || !email}
            className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-brand px-4 py-2 text-sm font-medium text-white hover:bg-brand-dark disabled:opacity-60"
          >
            {loading ? ct(dict, "login.sending") : ct(dict, "login.button")}
            <ArrowRight className="h-4 w-4" />
          </button>
          {error && <p className="text-sm text-red-400">{error}</p>}
        </form>
      ) : (
        <div className="mt-8 rounded-xl border border-slate-700 bg-slate-900 p-5">
          <div className="flex items-start gap-3">
            <CheckCircle2 className="mt-0.5 h-5 w-5 text-emerald-400" />
            <div className="text-sm">
              <p className="text-slate-200">
                {ct(dict, "login.sentToPrefix")}{" "}
                <span className="text-white">{email}</span>{" "}
                {smtpEnabled ? "" : ct(dict, "login.smtpDisabledNote")}
              </p>
              <p className="mt-2 text-slate-400">{ct(dict, "login.linkValidNote")}</p>
              {debugLink && (
                <div className="mt-4 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-xs text-amber-200">
                  <p className="font-medium">{ct(dict, "login.devModeTitle")}</p>
                  <p className="mt-1 text-amber-300/80">{ct(dict, "login.devModeBody")}</p>
                  <a
                    href={debugLink}
                    className="mt-2 block break-all text-amber-100 underline"
                  >
                    {debugLink}
                  </a>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <p className="mt-8 text-center text-xs text-slate-500">
        {ct(dict, "login.consent")}{" "}
        <Link href="/pricing" className="underline hover:text-slate-300">
          {ct(dict, "login.terms")}
        </Link>
        .
      </p>
    </main>
  );
}
