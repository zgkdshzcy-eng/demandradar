import { expect, test } from "@playwright/test";
import { apiRequest, loginAs, promoteToAdmin } from "./fixtures";

test.describe("admin · /admin gate + dashboard", () => {
  test("non-admin user gets 403 on /api/admin/stats", async ({ page }) => {
    const email = `e2e-noadmin-${Date.now()}@example.com`;
    const { token } = await loginAs(page, email);
    const api = await apiRequest();
    try {
      const r = await api.get("/api/admin/stats", {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(r.status()).toBe(403);
    } finally {
      await api.dispose();
    }
  });

  test("admin user can read /api/admin/stats and gets all sections", async ({ page }) => {
    const email = `e2e-admin-${Date.now()}@example.com`;
    const { token } = await loginAs(page, email);
    await promoteToAdmin(email);

    const api = await apiRequest();
    try {
      const r = await api.get("/api/admin/stats", {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(r.ok()).toBeTruthy();
      const body = await r.json();
      expect(body).toHaveProperty("cards");
      expect(body).toHaveProperty("plans");
      expect(body).toHaveProperty("recent_events");
      expect(body).toHaveProperty("top_referrers");
      const labels = body.cards.map((c: any) => c.label);
      expect(labels).toEqual(
        expect.arrayContaining(["Users", "Active subs", "Referral grants"]),
      );
    } finally {
      await api.dispose();
    }
  });

  test("admin SSR page renders the dashboard for admin users", async ({ page }) => {
    const email = `e2e-admin-ssr-${Date.now()}@example.com`;
    await loginAs(page, email);
    await promoteToAdmin(email);

    await page.goto("/admin");
    // Heading or some unique admin-only text
    await expect(page.getByText(/Users|用户|Active subs|MRR/i).first()).toBeVisible();
  });
});
