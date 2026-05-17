/**
 * Shared E2E helpers.
 *
 * - `loginAs(page, email)` performs a magic-link sign-in. Uses /api/auth/exchange
 *   for speed (no email round-trip) and sets the dr_session cookie directly.
 * - `promoteToAdmin(email)` flips the is_admin bit via a backend dev endpoint
 *   (only mounted when APP_SECRET_KEY is the default e2e key).
 */
import { request, type Page, type APIRequestContext } from "@playwright/test";

const BE = process.env.E2E_BACKEND_URL || `http://127.0.0.1:${process.env.E2E_PORT_BE || 8100}`;
const FE = process.env.E2E_FRONTEND_URL || `http://127.0.0.1:${process.env.E2E_PORT_FE || 3100}`;

export const URLS = { BE, FE };

export async function apiRequest(): Promise<APIRequestContext> {
  return request.newContext({ baseURL: BE });
}

/** Hits /api/auth/request-link and pulls the JWT out of debug_link. */
export async function fetchMagicToken(api: APIRequestContext, email: string): Promise<string> {
  const r = await api.post("/api/auth/request-link", { data: { email } });
  if (!r.ok()) throw new Error(`request-link failed: ${r.status()} ${await r.text()}`);
  const body = await r.json();
  if (!body.debug_link) {
    throw new Error("debug_link missing — backend SMTP_HOST should be empty in E2E");
  }
  // verify_url looks like: ${FE}/api/auth/verify?token=<jwt>
  const url = new URL(body.debug_link);
  const tok = url.searchParams.get("token");
  if (!tok) throw new Error(`no token in debug_link: ${body.debug_link}`);
  return tok;
}

/** Drops a dr_session cookie on the page so subsequent SSR navigations are
 *  authenticated. Uses /api/auth/exchange + a manual cookie set so we don't
 *  rely on the verify-redirect flow which can race the test. */
export async function loginAs(page: Page, email: string): Promise<{ token: string; user: any }> {
  const api = await apiRequest();
  try {
    const magic = await fetchMagicToken(api, email);
    const r = await api.post("/api/auth/exchange", { data: { token: magic } });
    if (!r.ok()) throw new Error(`exchange failed: ${r.status()}`);
    const { access_token } = await r.json();
    // Drop the cookie on both the FE host (for SSR pages) and BE host
    // (for client-side fetches against BE if any spec uses them).
    const feHost = new URL(FE).hostname;
    await page.context().addCookies([
      {
        name: "dr_session",
        value: access_token,
        domain: feHost,
        path: "/",
        httpOnly: true,
        sameSite: "Lax",
      },
    ]);
    // Verify
    const me = await api.get("/api/auth/me", {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    if (!me.ok()) throw new Error(`me failed after login: ${me.status()}`);
    return { token: access_token, user: await me.json() };
  } finally {
    await api.dispose();
  }
}

/** Issues a redeem code on the backend by hitting the dev backdoor (CLI-style).
 *  Uses an admin-token endpoint guarded by APP_SECRET_KEY for E2E only. */
export async function issueRedeemCode(plan: string, opts: { days?: number; brief_id?: number } = {}) {
  const api = await apiRequest();
  try {
    const r = await api.post(
      "/api/billing/_e2e/issue-code",
      {
        headers: { "X-Admin-Secret": process.env.APP_SECRET_KEY || "e2e-test-secret-key-do-not-use-in-prod" },
        data: { plan, ...opts },
      },
    );
    if (!r.ok()) throw new Error(`issue-code failed: ${r.status()} ${await r.text()}`);
    return (await r.json()).code as string;
  } finally {
    await api.dispose();
  }
}

export async function promoteToAdmin(email: string) {
  const api = await apiRequest();
  try {
    const r = await api.post(
      "/api/billing/_e2e/promote",
      {
        headers: { "X-Admin-Secret": process.env.APP_SECRET_KEY || "e2e-test-secret-key-do-not-use-in-prod" },
        data: { email },
      },
    );
    if (!r.ok()) throw new Error(`promote failed: ${r.status()}`);
  } finally {
    await api.dispose();
  }
}
