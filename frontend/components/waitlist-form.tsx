"use client";

import { useState } from "react";
import { Loader2, CheckCircle2 } from "lucide-react";

import { ct, readLocaleCookie, type ClientDict } from "@/lib/i18n-client";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

interface Props {
  dict?: ClientDict;
}

export function WaitlistForm({ dict = {} }: Props) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "ok" | "err">("idle");
  const [msg, setMsg] = useState<string>("");

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    setState("loading");
    setMsg("");
    try {
      const locale = readLocaleCookie();
      const r = await fetch(`${API}/api/waitlist`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, source: "landing", locale }),
      });
      if (!r.ok) {
        const body = await r.json().catch(() => ({}));
        throw new Error(body.detail || `HTTP ${r.status}`);
      }
      await r.json();
      setState("ok");
      setMsg(ct(dict, "waitlist.success"));
      setEmail("");
    } catch (err) {
      setState("err");
      const fallback = ct(dict, "waitlist.error");
      setMsg(err instanceof Error ? err.message || fallback : fallback);
    }
  }

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-2 sm:flex-row">
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder={ct(dict, "waitlist.placeholder") || "you@startup.com"}
        className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-3 text-sm text-white placeholder:text-slate-500 focus:border-brand focus:outline-none"
      />
      <button
        type="submit"
        disabled={state === "loading"}
        className="inline-flex items-center justify-center gap-2 rounded-lg bg-brand px-5 py-3 text-sm font-semibold text-white transition hover:bg-brand-dark disabled:opacity-60"
      >
        {state === "loading" ? (
          <Loader2 className="h-4 w-4 animate-spin" />
        ) : state === "ok" ? (
          <CheckCircle2 className="h-4 w-4" />
        ) : null}
        {state === "ok"
          ? ct(dict, "waitlist.success")
          : state === "loading"
            ? ct(dict, "waitlist.joining")
            : ct(dict, "waitlist.button")}
      </button>
      {msg && (
        <div
          className={`absolute mt-14 text-xs ${
            state === "ok" ? "text-emerald-400" : "text-rose-400"
          }`}
        >
          {msg}
        </div>
      )}
    </form>
  );
}
