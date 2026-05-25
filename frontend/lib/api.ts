/**
 * Typed API client.
 *
 * Uses NEXT_PUBLIC_API_URL on the client and INTERNAL_API_URL on the server
 * (e.g. talking to FastAPI inside docker network). Falls back to localhost.
 */

const API_BASE =
  (typeof window === "undefined"
    ? process.env.INTERNAL_API_URL || process.env.NEXT_PUBLIC_API_URL
    : process.env.NEXT_PUBLIC_API_URL) || "http://localhost:8000";

export type GoNoGo = "go" | "watch" | "drop";

export interface Evidence {
  id: number;
  source: string;
  url: string | null;
  title: string | null;
  quote: string;
}

export interface PainPoint {
  id: number;
  pain: string;
  scenario: string | null;
  target_user: string | null;
  frequency_signal: string;
  emotion: string;
  willingness_to_pay_signal: string;
  total_score: number | null;
  go_no_go: GoNoGo | null;
  rationale: string | null;
  cluster_id: number | null;
  cluster_label: string | null;
  scores: Record<string, number | null> | null;
  created_at: string;
  evidence: Evidence[];
}

export interface WeeklySummary {
  id: number;
  issue_no: number;
  title: string;
  period_start: string;
  period_end: string;
  status: string;
  items: number;
  created_at: string;
}

export interface WeeklyDetail extends WeeklySummary {
  markdown_preview: string;
  markdown_full: string | null;
  unlocked: boolean;
}

export interface BriefSummary {
  id: number;
  pain_point_id: number;
  title: string;
  visibility: string;
  version: number;
  total_score: number | null;
  pain: string | null;
  preview: string;
  created_at: string;
}

export interface BriefDetail extends BriefSummary {
  unlocked: boolean;
  markdown?: string;
}

export interface Entitlement {
  plans: string[];
  can_read_weekly_full: boolean;
  can_read_any_brief: boolean;
  unlocked_brief_ids: number[];
  is_admin: boolean;
}

export interface MeResponse {
  id: number;
  email: string;
  name: string | null;
  is_admin: boolean;
  entitlement: Entitlement;
  referral_code?: string | null;
  referral_url?: string | null;
}

export interface AdminStatsCard {
  label: string;
  value: number;
  note?: string | null;
}

export interface AdminPlanCount {
  plan: string;
  active: number;
  canceled: number;
  refunded: number;
}

export interface AdminRecentEvent {
  id: number;
  event_id: string;
  type: string;
  received_at: string;
  user_id: number | null;
  subscription_id: number | null;
}

export interface AdminTopReferrer {
  user_id: number;
  email: string;
  referral_code: string | null;
  grants: number;
  total_bonus_days: number;
}

export interface AdminStats {
  cards: AdminStatsCard[];
  plans: AdminPlanCount[];
  recent_events: AdminRecentEvent[];
  top_referrers: AdminTopReferrer[];
}

export interface SubscriptionRow {
  id: number;
  plan: string;
  status: string;
  provider: string;
  provider_ref: string | null;
  started_at: string | null;
  expires_at: string | null;
}

export interface SubscriptionResponse {
  user_id: number;
  items: SubscriptionRow[];
  entitlement: Entitlement;
}

export interface RequestLinkResponse {
  sent: boolean;
  smtp_enabled: boolean;
  debug_link: string | null;
}

export interface RedeemResponse {
  ok: boolean;
  plan: string;
  expires_at: string | null;
  brief_id: number | null;
  entitlement: Entitlement;
}

export interface CheckoutResponse {
  mode: "stripe" | "redeem_only";
  url: string | null;
  session_id: string | null;
  message: string;
}

export interface PortalResponse {
  url: string;
}

async function get<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const r = await fetch(url, {
    ...init,
    next: { revalidate: 60, ...(init as { next?: object })?.next },
  });
  if (!r.ok) {
    throw new Error(`API ${r.status} ${url}`);
  }
  return r.json() as Promise<T>;
}

async function getOrNull<T>(path: string): Promise<T | null> {
  try {
    return await get<T>(path);
  } catch {
    return null;
  }
}

/**
 * Server-side fetch that forwards the incoming request's Cookie header so
 * the backend can identify the logged-in user. Use only inside server
 * components / route handlers.
 */
export async function serverFetch<T>(
  path: string,
  cookieHeader: string | null,
  init?: RequestInit
): Promise<T | null> {
  try {
    const r = await fetch(`${API_BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        ...(init?.headers || {}),
        ...(cookieHeader ? { cookie: cookieHeader } : {}),
      },
    });
    if (!r.ok) return null;
    return (await r.json()) as T;
  } catch {
    return null;
  }
}

// ---------- D16: insights ----------

export interface InsightsHeatWeek {
  week_start: string;
  count: number;
}
export interface InsightsHeatRow {
  pain_point_id: number;
  pain: string;
  target_user: string | null;
  total_score: number | null;
  go_no_go: string | null;
  total: number;
  weeks: InsightsHeatWeek[];
}
export interface InsightsMover {
  pain_point_id: number;
  pain: string;
  target_user: string | null;
  total_score: number | null;
  this_week: number;
  last_week: number;
  delta: number;
  delta_pct: number | null;
}
export interface InsightsTimelinePoint {
  raw_signal_id: number;
  source: string;
  posted_at: string;
  title: string | null;
  text: string;
  url: string | null;
  score: number;
}

export interface ShareUnlockResponse {
  share_token: string;
  share_url: string;
  twitter_url: string | null;
  message: string;
}

export interface ClaimShareResponse {
  ok: boolean;
  brief_id: number | null;
  message: string;
}

export const api = {
  topPainpoints: (limit = 20) =>
    getOrNull<PainPoint[]>(`/api/painpoints/top?limit=${limit}`),
  painpoint: (id: number) => getOrNull<PainPoint>(`/api/painpoints/${id}`),

  // D16
  insightsHeat: (weeks = 6, limit = 30) =>
    getOrNull<InsightsHeatRow[]>(
      `/api/insights/heat?weeks=${weeks}&limit=${limit}`
    ),
  insightsMovers: (limit = 12) =>
    getOrNull<InsightsMover[]>(`/api/insights/movers?limit=${limit}`),
  insightsSources: (days = 30) =>
    getOrNull<Record<string, number>>(`/api/insights/sources?days=${days}`),
  insightsTimeline: (id: number, limit = 60) =>
    getOrNull<InsightsTimelinePoint[]>(
      `/api/insights/timeline/${id}?limit=${limit}`
    ),

  latestWeekly: () => getOrNull<WeeklyDetail>(`/api/weekly/latest`),
  weeklyList: (limit = 12) =>
    getOrNull<WeeklySummary[]>(`/api/weekly?limit=${limit}`),

  publicStats: () =>
    getOrNull<{
      users: number;
      subscribers: number;
      weekly_issues: number;
      briefs: number;
      pain_points_scored: number;
      signals_scanned: number;
      mrr_usd: number;
      last_issue_at: string | null;
      last_brief_at: string | null;
    }>(`/api/public/stats`),

  publicStatus: () =>
    getOrNull<{
      overall: "healthy" | "degraded" | "down";
      api: string;
      sources: Array<{
        name: string;
        state: "healthy" | "degraded" | "down";
        consecutive_failures: number;
        interval_mult: number;
        last_error: string | null;
      }>;
      recent_issues: Array<{
        issue_no: number;
        title: string;
        period_start: string;
        period_end: string;
        items: number;
      }>;
      last_signal_at: string | null;
    }>(`/api/public/status`),

  briefList: (limit = 12) =>
    getOrNull<{ total: number; items: BriefSummary[] }>(
      `/api/briefs?limit=${limit}`
    ),
  brief: (id: number, token?: string) =>
    getOrNull<BriefDetail>(
      `/api/briefs/${id}${token ? `?x_unlock_token=${encodeURIComponent(token)}` : ""}`
    ),

  // ---------- D10: auth ----------
  async requestLink(
    email: string,
    next?: string,
    ref?: string,
    locale?: string
  ): Promise<RequestLinkResponse | null> {
    try {
      const r = await fetch(`/api/auth/request-link`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email, next, ref, locale }),
      });
      if (!r.ok) return null;
      return (await r.json()) as RequestLinkResponse;
    } catch {
      return null;
    }
  },

  async logout(): Promise<boolean> {
    try {
      const r = await fetch(`/api/auth/logout`, { method: "POST" });
      return r.ok;
    } catch {
      return false;
    }
  },

  async me(): Promise<MeResponse | null> {
    try {
      const r = await fetch(`/api/auth/me`, { credentials: "include" });
      if (!r.ok) return null;
      return (await r.json()) as MeResponse;
    } catch {
      return null;
    }
  },

  // ---------- D12: billing checkout / portal ----------
  async checkout(input: {
    plan: "weekly_pro" | "studio" | "brief_oneoff";
    brief_id?: number;
  }): Promise<{ ok: true; data: CheckoutResponse } | { ok: false; error: string }> {
    try {
      const r = await fetch(`/api/billing/checkout`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      });
      if (!r.ok) {
        let msg = `error ${r.status}`;
        try {
          const j = await r.json();
          if (j?.detail) msg = String(j.detail);
        } catch {}
        return { ok: false, error: msg };
      }
      return { ok: true, data: (await r.json()) as CheckoutResponse };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  },

  async openPortal(): Promise<{ ok: true; url: string } | { ok: false; error: string }> {
    try {
      const r = await fetch(`/api/billing/portal`, { method: "POST" });
      if (!r.ok) {
        let msg = `error ${r.status}`;
        try {
          const j = await r.json();
          if (j?.detail) msg = String(j.detail);
        } catch {}
        return { ok: false, error: msg };
      }
      const j = (await r.json()) as PortalResponse;
      return { ok: true, url: j.url };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  },

  // ---------- D10: redeem ----------
  async redeem(code: string): Promise<{ ok: true; data: RedeemResponse } | { ok: false; error: string }> {
    try {
      const r = await fetch(`/api/billing/redeem`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ code }),
      });
      if (!r.ok) {
        let msg = `error ${r.status}`;
        try {
          const j = await r.json();
          if (j?.detail) msg = String(j.detail);
        } catch {}
        return { ok: false, error: msg };
      }
      return { ok: true, data: (await r.json()) as RedeemResponse };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  },

  // ---------- D20: share-to-unlock ----------
  async createShareUnlock(input: {
    brief_id?: number;
    pain_point_id?: number;
    platform?: string;
  }): Promise<ShareUnlockResponse | null> {
    try {
      const r = await fetch(`/api/billing/share-unlock`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(input),
      });
      if (!r.ok) return null;
      return (await r.json()) as ShareUnlockResponse;
    } catch {
      return null;
    }
  },

  async claimShareUnlock(
    share_token: string
  ): Promise<{ ok: true; data: ClaimShareResponse } | { ok: false; error: string }> {
    try {
      const r = await fetch(`/api/billing/share-unlock/claim`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ share_token }),
      });
      if (!r.ok) {
        let msg = `error ${r.status}`;
        try {
          const j = await r.json();
          if (j?.detail) msg = String(j.detail);
        } catch {}
        return { ok: false, error: msg };
      }
      return { ok: true, data: (await r.json()) as ClaimShareResponse };
    } catch (e) {
      return { ok: false, error: String(e) };
    }
  },
};
