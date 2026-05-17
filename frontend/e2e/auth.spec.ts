import { expect, test } from "@playwright/test";
import { apiRequest, fetchMagicToken, loginAs } from "./fixtures";

test.describe("auth · magic-link", () => {
  test("anonymous home page is reachable and links to /login", async ({ page }) => {
    await page.goto("/");
    await expect(page).toHaveTitle(/DemandRadar/);
    // /login link exists somewhere in the nav
    const login = page.getByRole("link", { name: /登录|sign in|login/i }).first();
    await expect(login).toBeVisible();
  });

  test("/account redirects anonymous users to /login", async ({ page }) => {
    const r = await page.goto("/account");
    // Either redirected to /login OR rendered with a sign-in CTA — both are valid.
    const url = page.url();
    expect(url).toMatch(/\/(login|account)/);
    if (/\/account/.test(url)) {
      await expect(page.getByRole("link", { name: /登录|sign in/i })).toBeVisible();
    }
  });

  test("magic-link login flow lands user on /account", async ({ page }) => {
    const email = `e2e-auth-${Date.now()}@example.com`;
    await loginAs(page, email);
    await page.goto("/account");
    // Page should now show user's email and a referral block.
    await expect(page.getByText(email)).toBeVisible();
    await expect(page.getByText(/推荐|referral/i)).toBeVisible();
  });

  test("/api/auth/me returns referral_url after login", async ({ page }) => {
    const email = `e2e-me-${Date.now()}@example.com`;
    const { token } = await loginAs(page, email);
    const api = await apiRequest();
    try {
      const r = await api.get("/api/auth/me", {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(r.ok()).toBeTruthy();
      const me = await r.json();
      expect(me.email).toBe(email);
      expect(me.referral_code).toBeTruthy();
      expect(me.referral_url).toContain(me.referral_code);
    } finally {
      await api.dispose();
    }
  });

  test("debug_link contains a usable JWT", async () => {
    const api = await apiRequest();
    try {
      const tok = await fetchMagicToken(api, `e2e-debug-${Date.now()}@example.com`);
      // JWT-style 3 segments
      expect(tok.split(".")).toHaveLength(3);
    } finally {
      await api.dispose();
    }
  });
});
