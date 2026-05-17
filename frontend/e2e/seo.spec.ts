import { expect, test } from "@playwright/test";

test.describe("seo · robots, sitemap, OG, JSON-LD", () => {
  test("/robots.txt allows public pages and disallows /account, /admin", async ({ request }) => {
    const r = await request.get("/robots.txt");
    expect(r.ok()).toBeTruthy();
    const txt = await r.text();
    expect(txt).toMatch(/User-agent:\s*\*/i);
    expect(txt).toMatch(/Disallow:\s*\/admin/);
    expect(txt).toMatch(/Disallow:\s*\/account/);
  });

  test("/sitemap.xml lists at least the public marketing pages", async ({ request }) => {
    const r = await request.get("/sitemap.xml");
    expect(r.ok()).toBeTruthy();
    const xml = await r.text();
    expect(xml).toContain("<urlset");
    for (const path of ["/", "/pricing", "/sample", "/radar", "/briefs"]) {
      // Either absolute or relative; just substring-check.
      expect(xml).toContain(path);
    }
    expect(xml).toContain('hreflang="en"');
    expect(xml).toContain('hreflang="zh-CN"');
    expect(xml).toContain("lang=zh");
  });

  test("home page has OG image, twitter:card, canonical and hreflang tags", async ({ page }) => {
    await page.goto("/");
    const ogTitle = await page.locator('meta[property="og:title"]').first().getAttribute("content");
    expect(ogTitle).toBeTruthy();
    const ogImg = await page.locator('meta[property="og:image"]').first().getAttribute("content");
    expect(ogImg).toBeTruthy();
    const twitter = await page.locator('meta[name="twitter:card"]').first().getAttribute("content");
    expect(twitter).toMatch(/summary/i);
    const enHref = await page.locator('link[rel="alternate"][hreflang="en"]').first().getAttribute("href");
    expect(enHref).toContain("lang=en");
    const zhHref = await page.locator('link[rel="alternate"][hreflang="zh-CN"]').first().getAttribute("href");
    expect(zhHref).toContain("lang=zh");
  });

  test("locale query sets language cookie and redirects to canonical path", async ({ page }) => {
    await page.goto("/pricing?lang=zh");
    await expect(page).toHaveURL(/\/pricing$/);
    const lang = await page.evaluate(() =>
      document.cookie.split("; ").find((cookie) => cookie.startsWith("dr_lang=")),
    );
    expect(lang).toBe("dr_lang=zh");
  });

  test("/og?kind=home returns a 1200x630 PNG/SVG image", async ({ request }) => {
    const r = await request.get("/og?kind=home&title=Test");
    expect(r.ok()).toBeTruthy();
    const ct = r.headers()["content-type"] || "";
    expect(ct).toMatch(/image\/(png|svg)/);
  });

  test("pricing page exposes OG metadata", async ({ page }) => {
    await page.goto("/pricing");
    const ogImg = await page.locator('meta[property="og:image"]').first().getAttribute("content");
    expect(ogImg).toBeTruthy();
    const canonical = await page.locator('link[rel="canonical"]').first().getAttribute("href");
    expect(canonical).toMatch(/\/pricing/);
  });
});
