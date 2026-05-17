import { expect, test } from "@playwright/test";
import { apiRequest, issueRedeemCode, loginAs } from "./fixtures";

test.describe("redeem · brief unlock flow", () => {
  test("user redeems weekly_pro code and gains entitlement", async ({ page }) => {
    const email = `e2e-redeem-pro-${Date.now()}@example.com`;
    const { token } = await loginAs(page, email);
    const code = await issueRedeemCode("weekly_pro", { days: 30 });

    const api = await apiRequest();
    try {
      const r = await api.post("/api/billing/redeem", {
        headers: { Authorization: `Bearer ${token}` },
        data: { code },
      });
      expect(r.ok()).toBeTruthy();
      const body = await r.json();
      expect(body.ok).toBe(true);
      expect(body.plan).toBe("weekly_pro");
      expect(body.entitlement).toMatchObject({ weekly_full: true });
    } finally {
      await api.dispose();
    }
  });

  test("brief_oneoff redeem unlocks ONLY the targeted brief", async ({ page }) => {
    // Seed two briefs.
    const seedA = await (await apiRequest()).post("/api/billing/_e2e/seed-brief", {
      headers: { "X-Admin-Secret": "e2e-test-secret-key-do-not-use-in-prod" },
      data: { title: "Target", pain: `e2e-tgt-${Date.now()}` },
    });
    const seedB = await (await apiRequest()).post("/api/billing/_e2e/seed-brief", {
      headers: { "X-Admin-Secret": "e2e-test-secret-key-do-not-use-in-prod" },
      data: { title: "Other", pain: `e2e-oth-${Date.now()}` },
    });
    const briefA = (await seedA.json()).brief_id;
    const briefB = (await seedB.json()).brief_id;

    const email = `e2e-redeem-brief-${Date.now()}@example.com`;
    const { token } = await loginAs(page, email);
    const code = await issueRedeemCode("brief_oneoff", { brief_id: briefA });

    const api = await apiRequest();
    try {
      const r = await api.post("/api/billing/redeem", {
        headers: { Authorization: `Bearer ${token}` },
        data: { code },
      });
      expect(r.ok()).toBeTruthy();

      // Brief A: should be unlocked (markdown returned)
      const a = await api.get(`/api/briefs/${briefA}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(a.ok()).toBeTruthy();
      const aBody = await a.json();
      expect(aBody.unlocked).toBe(true);

      // Brief B: should still be locked
      const b = await api.get(`/api/briefs/${briefB}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      expect(b.ok()).toBeTruthy();
      const bBody = await b.json();
      expect(bBody.unlocked).toBe(false);
    } finally {
      await api.dispose();
    }
  });

  test("re-using a redeem code is rejected (double-spend protection)", async ({ page }) => {
    const email = `e2e-double-${Date.now()}@example.com`;
    const { token } = await loginAs(page, email);
    const code = await issueRedeemCode("weekly_pro", { days: 30 });

    const api = await apiRequest();
    try {
      const r1 = await api.post("/api/billing/redeem", {
        headers: { Authorization: `Bearer ${token}` },
        data: { code },
      });
      expect(r1.ok()).toBeTruthy();

      const r2 = await api.post("/api/billing/redeem", {
        headers: { Authorization: `Bearer ${token}` },
        data: { code },
      });
      expect(r2.status()).toBeGreaterThanOrEqual(400);
    } finally {
      await api.dispose();
    }
  });
});
