"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut } from "lucide-react";

import { api } from "@/lib/api";
import { ct, type ClientDict } from "@/lib/i18n-client";

interface Props {
  dict: ClientDict;
}

export function LogoutButton({ dict }: Props) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function onClick() {
    setLoading(true);
    await api.logout();
    setLoading(false);
    router.push("/");
    router.refresh();
  }

  return (
    <button
      onClick={onClick}
      disabled={loading}
      className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 px-3 py-1.5 text-sm text-slate-300 hover:border-slate-500 hover:text-white"
    >
      <LogOut className="h-4 w-4" />{" "}
      {loading ? ct(dict, "logout.signingOut") : ct(dict, "logout.button")}
    </button>
  );
}
