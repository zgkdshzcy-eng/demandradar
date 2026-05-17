# DemandRadar E2E (Playwright)

End-to-end tests covering the critical user paths:

| Spec               | Covers                                                      |
| ------------------ | ----------------------------------------------------------- |
| `auth.spec.ts`     | Magic-link login, /account, /api/auth/me, referral_url      |
| `redeem.spec.ts`   | weekly_pro + brief_oneoff redeem, double-spend rejection    |
| `admin.spec.ts`    | /api/admin/stats gating + SSR /admin dashboard for admins   |
| `seo.spec.ts`      | robots.txt, sitemap.xml, OG meta, dynamic /og image, canon. |

## Run locally

```bash
cd frontend
npm install                  # picks up @playwright/test
npm run test:e2e:install     # downloads Chromium
npm run build                # next build (required for `next start`)
npm run test:e2e
```

The Playwright config in `frontend/playwright.config.ts` boots both servers on
unique ports (`8100` backend, `3100` frontend) using a throw-away SQLite file
(`backend/e2e_test.db`) — your dev DB and dev ports are untouched.

## E2E backdoor endpoints

The Playwright suite drives the backend through `/api/billing/_e2e/*`
endpoints which only exist when `E2E_ENABLE=1`. They are guarded by the
`X-Admin-Secret` header which must equal `APP_SECRET_KEY`. **Never set
`E2E_ENABLE=1` in production.**

- `POST /_e2e/issue-code` — mint a redeem code (mirrors the CLI command)
- `POST /_e2e/promote`    — flip a user's `is_admin` to true
- `POST /_e2e/seed-brief` — seed a paid Brief + PainPoint pair

## CI

GitHub Actions runs the same `npm run test:e2e` after `pip install -e .[dev]`
in the backend and `npm ci` in the frontend. See
`.github/workflows/e2e.yml`.
