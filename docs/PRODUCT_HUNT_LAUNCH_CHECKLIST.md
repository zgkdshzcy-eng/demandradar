# DemandRadar Product Hunt Launch Checklist

## Positioning

- **Tagline**: DemandRadar — Find high-willingness-to-pay SaaS ideas before you build.
- **One-liner**: We scan public communities and ship the Top-20 demand signals plus build-ready project briefs every week.
- **Audience**: Indie hackers, solo founders, micro-SaaS builders, AI builders, product studios.
- **Primary promise**: Spend less time guessing what to build and more time validating monetizable pain points.

## Assets

- **Logo**: Prepare square PNG/SVG at 240x240 and 1024x1024.
- **Gallery images**: Include landing page, radar, weekly digest, brief detail, and pricing screenshots.
- **OG image**: Verify `/og?kind=home` renders correctly at 1200x630.
- **Demo URL**: Use the production `NEXT_PUBLIC_SITE_URL` root URL.
- **Sample brief URL**: Use `/sample` or a public `/briefs/{id}` preview.

## Launch copy

- **Headline**: Stop guessing SaaS ideas. Track real demand signals weekly.
- **Short description**: DemandRadar mines Reddit, Hacker News, GitHub, reviews, and founder communities to surface urgent pains and build-ready SaaS briefs.
- **Maker comment structure**:
  - **Problem**: Builders waste weeks on ideas without demand.
  - **Solution**: DemandRadar continuously mines public signals and summarizes monetizable pains.
  - **What is new**: English-first launch, Chinese support, USD Stripe subscriptions, weekly Top-20 radar, project briefs.
  - **Ask**: Invite feedback on data sources, brief format, and pricing.

## SEO and i18n preflight

- **Hreflang**: Confirm home page emits `en`, `zh-CN`, and `x-default` alternates.
- **Sitemap**: Confirm `/sitemap.xml` includes public pages and language alternates.
- **Robots**: Confirm `/robots.txt` allows marketing pages and disallows private routes.
- **Canonical**: Confirm public pages expose canonical URLs without query parameters.
- **Language switch**: Confirm `?lang=en` and `?lang=zh` set `dr_lang` and redirect to canonical paths.

## Stripe and onboarding preflight

- **Live mode keys**: Set `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, and USD price IDs in production.
- **Checkout flow**: Verify Weekly Pro, Studio, and one-off brief checkout in live mode with a low-risk test account.
- **Webhook flow**: Verify successful payment updates entitlement and sends localized email.
- **Portal flow**: Verify customers can manage billing from `/account`.
- **Email locale**: Verify magic link, waitlist, payment confirmation, and newsletter emails render in English and Chinese.

## Launch-day operations

- **Monitoring**: Watch frontend logs, backend logs, Stripe webhook delivery, and email provider delivery.
- **Support channel**: Keep a single reply template for billing, login, and data-source feedback.
- **Analytics**: Track visits to `/`, `/pricing`, `/sample`, `/briefs`, and checkout starts.
- **Community posts**: Prepare short posts for X, Hacker News, Indie Hackers, Reddit, and relevant Discord/Slack groups.
- **Follow-up**: Within 24 hours, summarize feedback into pricing, positioning, data-source, and product-roadmap buckets.
