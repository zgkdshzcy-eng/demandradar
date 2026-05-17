# Stripe USD setup (international rollout)

Step-by-step playbook for wiring a fresh Stripe account so DemandRadar can
charge `$9.9 / mo` (Pro Weekly), `$29 / mo` (Studio), and `$29 one-time`
(single brief unlock) to international customers.

If you only need WeChat / Alipay redeem-code mode, you can skip everything
below — leave `STRIPE_SECRET_KEY` empty and ship redeem codes via email.

---

## 0. What you need first

- A Stripe account that has **finished onboarding** and is **out of test mode**
  for whichever country you operate in. Pricing and tax behaviour change once
  the account is activated, so always re-run the smoke test against live keys
  before announcing.
- A registered domain on HTTPS for production webhooks. Stripe rejects HTTP
  endpoints and self-signed certs in live mode.
- The Stripe CLI installed locally for testing. On Windows:
  ```powershell
  scoop install stripe         # or: choco install stripe-cli
  stripe login                 # opens browser, links your account
  ```

> **Default currency**: when activating the account choose `USD` as the
> default settlement currency. You can later add EUR/GBP price tiers without
> recreating the products.

---

## 1. Create the Products

Stripe Dashboard → **Product catalog → Add product**. Create three products,
each with the price listed below. Match the names exactly so support /
webhook logs are unambiguous.

| Product name (Stripe)         | Price            | Mode         | Plan key         |
|-------------------------------|------------------|--------------|------------------|
| DemandRadar Pro Weekly        | `$9.90 / month`  | Recurring    | `weekly_pro`     |
| DemandRadar Studio            | `$29.00 / month` | Recurring    | `studio`         |
| DemandRadar Single Brief      | `$29.00 one-off` | One-time     | `brief_oneoff`   |

Recommended product settings:

- **Tax behaviour**: pick **"Inclusive"** if you display tax-inclusive
  pricing on the site; pick **"Exclusive"** if Stripe Tax should add the
  buyer's local VAT/GST on top. Staying consistent matters more than the
  choice itself — picking inclusive for one product and exclusive for
  another guarantees future you a confused refund email.
- **Payment methods**: enable card + Apple Pay + Google Pay + Link by
  default. Add region-specific methods (SEPA, iDEAL, Alipay, WeChat Pay) on
  the **Payment methods** tab once you start running campaigns there.
- **Allow promotion codes**: leave on; the existing checkout session
  already passes `allow_promotion_codes=True`.

After creating each price, copy the **price id** (looks like
`price_1OABcDeFgHiJkLmN`) — you'll paste those into env vars next.

---

## 2. Configure the Customer Portal

Dashboard → **Settings → Billing → Customer portal**. Enable:

- **Update payment method**
- **Cancel subscriptions** → "At the end of the billing period"
- **Switch plans** → optional; only enable once you stabilise the price
  catalogue (otherwise customers can self-downgrade mid-month).
- **Invoice history**

Set the **default return URL** to `https://<your-domain>/account`. This is
where Stripe drops users after they finish editing their subscription —
matches the value the backend passes via
`payments.create_billing_portal_session(..., return_url=...)`.

---

## 3. Configure Stripe Tax (recommended for EU/UK/AU buyers)

Dashboard → **Settings → Tax**. Switch to **Automatic tax** and:

1. Add registrations for each country / state where you've crossed (or
   expect to cross) the local threshold. For a brand-new product, registering
   in the EU OSS scheme + UK VAT once you have ~50 EU/UK customers is the
   usual pattern.
2. Enable **Tax IDs** on the Customer Portal so business buyers can supply
   their VAT number and we apply reverse-charge automatically.

If you skip this section now, Stripe charges flat-rate USD and you carry the
VAT compliance risk yourself. Easy to retrofit later — just turn it on and
new invoices include tax.

---

## 4. Configure the webhook

DemandRadar relies on `checkout.session.completed`, `invoice.paid`,
`invoice.payment_failed`, `customer.subscription.updated`,
`customer.subscription.deleted`, and `charge.refunded`. The endpoint code
lives in `backend/app/billing/webhook.py`.

### 4a. Local development

```powershell
# In one terminal: forward webhooks to your local API
stripe listen --forward-to http://localhost:8000/api/billing/webhook/stripe
# It prints a `whsec_...` secret. Copy it into backend/.env:
#   STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxxxx

# In another terminal: trigger a test event
stripe trigger checkout.session.completed
```

You should see a `webhook: subscription activated` line in the API log and
a new row in the `subscriptions` table.

### 4b. Production

Dashboard → **Developers → Webhooks → Add endpoint**:

- **Endpoint URL**: `https://<your-domain>/api/billing/webhook/stripe`
- **Listen to**: select **"Events on your account"** (not Connect).
- **Events**: subscribe to *exactly* these:
  - `checkout.session.completed`
  - `invoice.paid`
  - `invoice.payment_succeeded` (alias treated identically)
  - `invoice.payment_failed`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `charge.refunded`

Reveal the **signing secret** (`whsec_…`) and put it into `STRIPE_WEBHOOK_SECRET`.
Restart the API container so the new value is picked up.

> The webhook handler always returns HTTP 200 (even on internal errors) so
> Stripe stops retrying. Failures are persisted as a `<type>__failed` row
> in `payment_events` and surfaced in `/admin`. Watch that surface during
> the first week.

---

## 5. Wire env vars

Copy three price IDs into `backend/.env` (dev) or `.env.prod` (prod):

```env
# ----- Stripe -----
STRIPE_SECRET_KEY=sk_live_xxx                # use sk_test_xxx in dev
STRIPE_WEBHOOK_SECRET=whsec_xxx              # from `stripe listen` or dashboard

STRIPE_PRICE_WEEKLY_PRO=price_1xxx           # $9.90 / month recurring
STRIPE_PRICE_STUDIO=price_1xxx               # $29.00 / month recurring
STRIPE_PRICE_BRIEF_ONEOFF=price_1xxx         # $29.00 one-off

PUBLIC_BASE_URL=https://demandradar.example.com   # used to build success/cancel URLs
```

The price → plan mapping is enforced in
`backend/app/core/payments.py::plan_to_price_id`. If a price id is empty,
that plan's `Buy` button returns the friendly *"Stripe is not configured"*
message instead of crashing.

Restart `api` (and `web`, since the frontend caches `/api/auth/me` for 60s
on the SSR side):

```bash
docker compose --env-file .env.prod -f docker-compose.prod.yml up -d api web
```

---

## 6. Smoke test (in production)

```bash
# 1. Anonymous landing renders pricing in USD
curl -fsS https://<domain>/pricing | grep -i '\$9.9'

# 2. Logged-in user can create a Checkout Session
TOKEN=$(make issue-code plan=weekly_pro days=0)   # bypass real payment
# (or sign in via magic link, then in the browser dev tools:)
fetch('/api/billing/checkout', {
  method: 'POST',
  credentials: 'include',
  headers: {'content-type':'application/json'},
  body: JSON.stringify({plan: 'weekly_pro'})
}).then(r=>r.json()).then(console.log)
# expect: {mode: 'stripe', url: 'https://checkout.stripe.com/...'}

# 3. Pay with the universal Stripe test card 4242 4242 4242 4242 (in test
#    mode) and verify:
#    - the user is redirected to /account?paid=1
#    - /api/auth/me reports can_read_weekly_full=true within 5s
#    - paid-confirmation email arrives (when SMTP is configured)
#    - admin /admin shows the event in "Recent payment events"

# 4. Cancel from the customer portal and verify status flips to 'canceled'
#    on the next invoice cycle.
```

If step 2 returns `mode: 'redeem_only'`, the API is still seeing an empty
`STRIPE_SECRET_KEY` — restart the container after editing the env file.

---

## 7. Updating prices later

1. Create a **new price** under the existing product (don't edit the active
   one — Stripe locks the amount once it's used by a live subscription).
2. Update `STRIPE_PRICE_*` in `.env.prod` to point to the new price id.
3. Restart `api`. New checkouts use the new price; existing subscribers
   continue on the old one until they cancel + re-subscribe (or you migrate
   them via the CLI: `stripe subscriptions update sub_xxx --items[0].price=price_new`).

Keep both old and new price IDs documented somewhere (this file is fine) —
when reading historic Stripe events you'll need the old id to trace amounts.

---

## 8. Refund / cancellation flow

`POST /api/billing/refund/<subscription_id>` is admin-only and:

1. Cancels the recurring subscription at Stripe (no proration).
2. Refunds the most recent charge (one-time payments only).
3. Marks the local `Subscription.status` as `refunded` or `canceled`.

Tracked in `payment_events` so you can audit it later. We do **not** auto-issue
refunds from the public site — every refund goes through admin or via Stripe
Dashboard, which fires `charge.refunded` and converges the local row anyway.

---

## 9. FAQ

**"My checkout button does nothing in dev"**
The dev container's API has empty `STRIPE_SECRET_KEY`, so checkout returns
`mode: 'redeem_only'`. To test the real flow locally either fill in
`sk_test_...` + the three test price ids, or use `make issue-code` to
short-circuit billing entirely.

**"Webhook events arrive but the subscription never activates"**
Check the API log for `webhook: missing plan in metadata`. Stripe Checkout
Sessions only forward `metadata` if you explicitly set it — the backend
already does (`metadata={"user_id": ..., "plan": ...}`), but if you trigger
events with `stripe trigger`, the synthetic events have empty metadata, so
they intentionally no-op.

**"Customer is in EU and got charged in USD without VAT"**
You skipped step 3. Either enable Stripe Tax now (it'll apply on next
invoice) or issue a manual credit note for the missing VAT.

**"Card declined: `card_declined - generic_decline` in test mode"**
Use one of Stripe's test cards. `4242 4242 4242 4242` always succeeds.
[Full list](https://stripe.com/docs/testing).

---

## 10. Reference

- Backend integration: `backend/app/core/payments.py` (Checkout / Portal /
  refund), `backend/app/billing/webhook.py` (event handlers),
  `backend/app/api/billing.py` (HTTP endpoints).
- Frontend trigger: `frontend/components/checkout-button.tsx` —
  client-side calls `/api/billing/checkout`, redirects to
  `session.url`.
- Tests: `backend/tests/test_billing_stripe.py` exercises the
  webhook handler with synthetic events; `backend/tests/test_billing_e2e.py`
  drives the full activation path.
