# BackIt API contract (v1)

Shared contract between `apps/web` (Next.js) and `services/api` (FastAPI). Once implemented, FastAPI's `/openapi.json` is the source of truth; this file fixes names and shapes so both sides can be built in parallel.

## Conventions

- Base URL: `http://localhost:8000/v1` locally (`NEXT_PUBLIC_API_URL`).
- JSON, `snake_case` fields. Money is integer USD cents (`*_cents`). Rates are basis points (`*_bps`, 800 = 8%). Timestamps are UTC ISO-8601.
- IDs are prefixed strings: `prod_`, `cmp_`, `ord_`, `bck_`, `com_`, `pp_` (payout preview), `pb_` (payout batch), `evt_`, `dlv_`.
- Auth: `Authorization: Bearer <jwt>` from Better Auth's JWT plugin (`GET /api/auth/token` on the web origin returns `{ token }`). FastAPI verifies it against `AUTH_JWKS_URL` (default `http://localhost:3000/api/auth/jwks`) with algorithm EdDSA (Ed25519, OKP keys), issuer and audience `AUTH_ISSUER` (default `http://localhost:3000`). `sub` is the user ID; `email` and `name` claims are present. The first authenticated call upserts a profile.
- Mutating financial calls (`POST .../orders`, `/capture`, `/refund`, `/approve`) accept `Idempotency-Key`. Reuse with a different body returns `409 idempotency_key_reused`.
- Errors: `{"error": {"code": "snake_case", "message": "Human readable", "request_id": "req_...", "details": {}}}`. Use 401, 403, 404, 409 (conflict, stale preview, sold out), 422 (validation), 502 (provider failure), and 202 with `state: "pending_provider"` for uncertain provider outcomes.
- `PAYPAL_MODE=mock|sandbox`. In `mock` mode no PayPal call is made: onboarding connects instantly with merchant ID `MOCKMERCHANT…`, orders return `provider: "mock"`, and capture succeeds. Everything else (ledger, commissions, webhooks, payout state machine) runs for real. Mock data is always labelled.
- AI: OpenRouter when `OPENROUTER_API_KEY` is set; otherwise a deterministic template with `source: "template"`. Responses always carry `source: "ai" | "template"`.

## Config

`GET /config` (public) -> `{ paypal_mode: "mock"|"sandbox", paypal_client_id: str|null, ai_enabled: bool, platform_fee_bps: 800, hold_days: 30, payout_minimum_cents: 100, environment: "development"|"production" }`

## Identity

`GET /me` -> `Me`

```
Me { profile: Profile, products: ProductSummary[], backings: BackingSummary[] }
Profile { id, email, display_name, payout_email: str|null, payout_email_verified: bool }
ProductSummary { id, name, slug, campaign: { id, slug, status, headline } | null }
BackingSummary { id, campaign_slug, campaign_headline, badge_number: int|null, kind: "founding"|"referral" }
```

`PATCH /me` `{ display_name?, payout_email? }` -> `Profile`. In sandbox, setting a payout email marks it verified and records an audit event labelled as sandbox verification.

## Products and onboarding

```
Product {
  id, name, slug, url, description, access_terms, refund_terms,
  webhook_url: str|null, webhook_secret_hint: str|null,  // last 4 chars only
  seller: SellerConnection,
  verification: Verification|null,
  campaign: Campaign|null,
  created_at
}
SellerConnection { status: "not_connected"|"pending"|"connected"|"failed", merchant_id: str|null, provider: "mock"|"paypal_sandbox", checked_at: str|null, payments_receivable: bool }
Verification { source: "demo"|"paypal"|"stripe", is_demo: bool, months: [{ month: "YYYY-MM", revenue_cents }], threshold_cents: 100000, threshold_met: bool, checked_at }
```

- `POST /products` `{ name, url, description, access_terms, refund_terms?, webhook_url? }` -> `ProductCreated` = `Product` + `webhook_secret` (the full secret is returned once).
- `GET /products/{id}` -> `Product` (owner only).
- `PATCH /products/{id}` partial create body -> `Product`.
- `POST /products/{id}/webhook-secret/rotate` -> `{ webhook_secret }`.
- `POST /products/{id}/paypal/onboarding` -> `{ status, action_url: str|null }` (mock connects immediately; sandbox returns a Partner Referrals link).
- `GET /products/{id}/paypal/status` -> `SellerConnection` (server-side capability check).
- `POST /products/{id}/verification/demo` `{ months: [revenue_cents, revenue_cents, revenue_cents] }` (oldest first) -> `Verification` with `is_demo: true`. Threshold: each of three consecutive months >= 100000 cents.
- `POST /products/{id}/webhook-test` -> `WebhookDelivery` (sends a `ping` event).

## Campaigns

```
Campaign {
  id, product_id, slug, status: "draft"|"published"|"closed", version,
  headline, summary, story,
  founding_price_cents, founding_spots_cap, founding_spots_taken,
  referral_list_price_cents, referral_discount_bps, commission_bps, platform_fee_bps,
  published_at: str|null, updated_at
}
CampaignDraft { headline, summary, story, founding_price_cents, founding_spots_cap, referral_list_price_cents, referral_discount_bps, commission_bps, disclosure, missing_evidence: str[], source: "ai"|"template", ai_run_id: str|null }
Readiness { ready: bool, checks: [{ key, label, ok: bool, detail: str|null }] }
```

- `POST /products/{id}/campaign-draft` `{ source_text?: str }` -> `CampaignDraft` (never saved or published automatically).
- `POST /campaigns` `{ product_id, slug, headline, summary, story, founding_price_cents, founding_spots_cap, referral_list_price_cents, referral_discount_bps, commission_bps }` -> `Campaign` (one campaign per product for the MVP; `409 campaign_exists`).
- `GET /campaigns/{id}`, `PATCH /campaigns/{id}` (price fields are editable only while in draft) -> `Campaign`.
- `GET /campaigns/{id}/readiness` -> `Readiness` (seller connected, verification threshold met, webhook URL set, valid prices where commission + platform fee < referral price after discount, and a free slug).
- `POST /campaigns/{id}/publish` -> `Campaign`; returns `409 not_ready` with `details.checks` when not ready.

Validation: prices 100..1_000_000 cents; `referral_discount_bps` 0..5000; `commission_bps` 0..5000; spots 1..10000; slug matches `^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$`, and reserved words are rejected.

## Public

```
PublicCampaign {
  id, slug, headline, summary, story, status,
  product: { name, url }, builder_name,
  founding: { price_cents, spots_cap, spots_taken, spots_left },
  referral: { list_price_cents, discount_bps, price_cents, commission_bps, commission_cents },
  platform_fee_bps,
  trust: { verification: Verification|null, seller_connected: bool, seller_provider, access_terms, refund_terms, hold_days, payout_minimum_cents },
  stats: { backers: int, sales: int },
  referrer: { code, display_name } | null      // when ?ref=CODE is valid
}
LedgerItem { ref (short pseudonymous), type: "founding_purchase"|"referral_purchase"|"refund"|"commission_earned"|"commission_reversed"|"payout_paid", amount_cents, occurred_at }
```

- `GET /public/campaigns/{slug}?ref=CODE` -> `PublicCampaign` (published campaigns only; otherwise 404).
- `GET /public/campaigns/{slug}/ledger?cursor=` -> `{ items: LedgerItem[], next_cursor: str|null }`.

## Checkout

```
Order {
  id, campaign_id, campaign_slug, kind: "founding"|"referral",
  state: "created"|"completed"|"cancelled"|"failed"|"refunded"|"pending_provider",
  list_price_cents, discount_cents, amount_cents, platform_fee_cents, commission_cents,
  referral_code: str|null, provider: "mock"|"paypal_sandbox", paypal_order_id: str|null,
  reservation_expires_at: str|null,
  backing: { id, badge_number: int|null, referral_code, share_url } | null,
  access: { status: "pending"|"delivered"|"failed"|"not_configured", last_attempt_at: str|null },
  created_at
}
```

- `POST /campaigns/{id}/orders` `{ kind, referral_code? }` -> `Order` (`state: "created"`). `kind="referral"` requires a valid code that is not the buyer's own (`422 invalid_referral_code`, `422 self_referral`). Founding purchases are limited to one per user per campaign (`409 already_backed`) and reserve a spot for 15 minutes (`409 sold_out`).
- `POST /orders/{id}/capture` -> `Order` (`completed`, or `202` with `pending_provider`).
- `POST /orders/{id}/cancel` -> `Order` (releases the reservation).
- `GET /orders/{id}` -> `Order` (buyer or campaign owner).

Pricing is calculated only by the backend. For a founding purchase, `amount = founding_price`. For a referral purchase:

- `discount = round_half_up(list × discount_bps / 10000)`
- `amount = list − discount`
- `commission = round_half_up(amount × commission_bps / 10000)`
- `platform_fee = round_half_up(amount × platform_fee_bps / 10000)`

Example: a 10000-cent list price with a 20% discount produces an 8000-cent amount, a 640-cent fee, and a 2000-cent commission at 25%.

Every completed purchaser, founding or referral, receives a backing with a referral code. Founding backers also receive a permanent badge number.

## Backer workspace

```
Backing {
  id, kind, campaign: { id, slug, headline, product_name }, badge_number, referral_code, share_url,
  balances: { held_cents, payable_cents, reserved_cents, paid_cents, reversed_cents },
  commissions: [{ id, order_ref, amount_cents, state: "held"|"payable"|"reserved"|"submitted"|"paid"|"reversed"|"blocked", release_at, created_at }],
  created_at
}
ShareDraft { channel, text }
```

- `GET /me/backings` -> `Backing[]`.
- `POST /backings/{id}/share-drafts` `{ channel: "x"|"linkedin"|"email", context?: str }` -> `{ drafts: ShareDraft[], source }`. Every draft includes a commission disclosure.

## Builder workspace

```
SalesSummary {
  totals: { orders, captured_cents, refunded_cents, platform_fee_cents, commission_liability_cents, commission_paid_cents },
  orders: [{ id, kind, state, buyer_label (masked), referral_code, amount_cents, platform_fee_cents, commission_cents, created_at }]
}
WebhookDelivery { id, event_id, event_type, state: "pending"|"delivered"|"failed"|"dead", attempts, last_status_code: int|null, last_error: str|null, next_attempt_at: str|null, created_at }
RiskFlag { id, rule, severity, status, evidence: {}, explanation: str|null, created_at }
```

- `GET /products/{id}/sales` -> `SalesSummary`.
- `POST /orders/{id}/refund` -> `Order` (owner only, full refunds only). It cancels held commission and creates reversal entries if the commission was already paid.
- `GET /products/{id}/webhook-deliveries` -> `WebhookDelivery[]`; `POST /webhook-deliveries/{id}/retry` -> `WebhookDelivery`.
- `GET /products/{id}/risk-flags` -> `RiskFlag[]`.

## Payouts

```
PayoutPreview {
  id, product_id, status: "open"|"approved"|"stale"|"expired",
  digest, total_cents, currency: "USD",
  items: [{ backing_id, backer_name, payout_email_masked, amount_cents, commission_ids: str[] }],
  exclusions: [{ backing_id, backer_name, amount_cents, reason: "below_minimum"|"in_hold"|"no_payout_email"|"risk_review"|"refund_pending" }],
  funding: { source: "sandbox_sender", available_cents: int|null, required_cents, sufficient: bool|null },
  explanation: { text, source: "ai"|"template" },
  created_at, expires_at
}
PayoutBatch { id, product_id, preview_id, status: "queued"|"submitted"|"processing"|"success"|"partial"|"failed", sender_batch_id, provider_batch_id: str|null, total_cents, items: [{ id, backer_name, amount_cents, status: "queued"|"submitted"|"pending"|"success"|"unclaimed"|"failed"|"returned", provider_item_id: str|null }], approved_by, approved_at, summary: str|null }
```

- `POST /products/{id}/payout-previews` -> `PayoutPreview`.
- `GET /payout-previews/{id}` -> `PayoutPreview`.
- `POST /payout-previews/{id}/approve` `{ digest, funding_confirmed: bool }` -> `PayoutBatch` (`409 stale_preview` if anything changed).
- `GET /payout-batches/{id}` -> `PayoutBatch`; `GET /products/{id}/payout-batches` -> `PayoutBatch[]`.
- `POST /products/{id}/dev/release-holds` (only when `ENVIRONMENT=development`; owner only; audited) -> `{ released: int }`. It moves hold release dates to now for demos.

## Incoming webhooks

- `POST /webhooks/paypal` verifies the event, stores it in `provider_events`, and returns 200 quickly.

## Builder webhooks

Headers:

- `BackIt-Event-Id`
- `BackIt-Timestamp` (Unix seconds)
- `BackIt-Signature: v1=<hex hmac_sha256(secret, f"{timestamp}.{raw_body}")>`
- `BackIt-Key-Version`

The body follows plan §8. Events: `ping`, `purchase.completed`, and `refund.issued`.
