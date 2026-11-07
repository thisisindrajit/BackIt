# 🏗️ BackIt architecture

This guide shows how BackIt works under the hood: the parts, how money moves, and what keeps it safe.
The diagrams use [Mermaid](https://mermaid.js.org/), so they render on GitHub.

> 📜 For exact request and response shapes, see [`api-contract.md`](api-contract.md).

## Contents

1. [The big picture](#-the-big-picture)
2. [The pieces](#-the-pieces)
3. [Sign-in and API auth](#-sign-in-and-api-auth)
4. [Two kinds of deals](#-two-kinds-of-deals)
5. [Checkout with PayPal](#-checkout-with-paypal)
6. [Referral rewards: from sale to payout](#-referral-rewards-from-sale-to-payout)
7. [Refunds](#-refunds)
8. [Telling the builder's app: webhooks and access codes](#-telling-the-builders-app-webhooks-and-access-codes)
9. [Where AI helps (and where it doesn't)](#-where-ai-helps-and-where-it-doesnt)
10. [The worker](#-the-worker)
11. [State machines](#-state-machines)
12. [Data model](#-data-model)
13. [Deployment](#-deployment)
14. [Safety rules we never break](#-safety-rules-we-never-break)

---

## 🗺️ The big picture

```mermaid
flowchart LR
    subgraph People
        B([👩‍💻 Builder])
        F([🙌 Founding backer])
        R([👋 Referred friend])
        V([🔎 Visitor])
    end

    subgraph Vercel
        WEB[Next.js web app<br/>backit.club<br/>+ Better Auth]
    end

    subgraph GCP["Google Cloud (us-central1)"]
        API[FastAPI API<br/>api.backit.club]
        WRK[Worker job<br/>every minute]
        DB[(Postgres 16<br/>schemas: app, auth)]
        SM[[Secret Manager]]
    end

    PP[💙 PayPal<br/>Orders · Partner Referrals<br/>Payouts · Webhooks]
    AI[🤖 OpenRouter<br/>LLM]
    MAIL[✉️ Resend<br/>email]
    DEMO[🧩 Builder's app<br/>e.g. Ledgerly demo]

    B & F & R & V --> WEB
    WEB -- "JWT (EdDSA)" --> API
    WEB -- "auth tables" --> DB
    API --> DB
    WRK --> DB
    API <--> PP
    WRK <--> PP
    API --> AI
    WRK --> MAIL
    WRK -- "signed webhooks" --> DEMO
    DEMO -- "redeem access code" --> API
    PP -- "webhooks" --> API
    SM -.-> API & WRK
```

**In one line:** the web app is the face, the API owns every rule about money, the worker does slow and retryable jobs, and PayPal moves the actual cash.

---

## 🧱 The pieces

| Piece | Tech | Where it lives | What it does |
|---|---|---|---|
| 🌐 Web app | Next.js 16, React 19, shadcn/ui, Tailwind v4, TanStack Query | Vercel, `backit.club` | Landing, Explore, campaign pages, checkout, builder and backer dashboards |
| 🔐 Auth | Better Auth (Google sign-in, JWT plugin) | Inside the web app, `auth` schema | Signs users in and issues short-lived JWTs for the API |
| ⚡ API | FastAPI, SQLAlchemy, Pydantic, Alembic | Cloud Run service `backit-api` | Every rule: pricing, checkout, refunds, holds, payouts, risk, ledger |
| ⏱️ Worker | Same code, `python -m app.workers.run --once` | Cloud Run job `backit-worker` | Outbox jobs, PayPal event inbox, builder webhooks, emails, holds, order expiry |
| 🗄️ Database | Postgres 16 | Managed Postgres / local | `app` schema for BackIt, `auth` schema for Better Auth |
| 💙 Payments | PayPal Orders v2, Partner Referrals, Payouts, Webhooks | PayPal sandbox | Takes payments, onboards builders, pays backers |
| 🤖 AI | OpenRouter with JSON-schema output | External | Drafts, offer advice, share posts, payout and risk explanations |
| ✉️ Email | Resend | External | Sale and payout notifications (skipped when no key is set) |
| 🧩 Demo product | FastAPI + SQLite | Cloud Run `backit-test-app` | A pretend builder app ("Ledgerly") that receives webhooks |

### Code map

```mermaid
flowchart TB
    subgraph web["apps/web/src"]
        pages["app/ — routes<br/>/, /explore, /[slug], /checkout, /app/*"]
        comps["components/ — landing, explore, builder,<br/>backer, dashboard, public, ui (shadcn)"]
        lib["lib/ — auth, auth-client, api client<br/>(typed from OpenAPI), format"]
    end
    subgraph api["services/api/app"]
        routers["routers/ — HTTP under /v1"]
        services["services/ — checkout, refunds, payouts,<br/>risk, risk_review, ledger, offers,<br/>campaigns, sharing, claims, deliveries"]
        providers["providers/ — paypal.py (mock + sandbox)<br/>ai.py (OpenRouter + templates)"]
        core["money.py · models.py · auth.py<br/>webhooks_out.py · email.py"]
        workers["workers/run.py"]
    end
    pages --> comps --> lib
    lib -- "fetch + JWT" --> routers
    routers --> services --> providers
    services --> core
    workers --> services
```

The web app's API types are generated from FastAPI's OpenAPI schema (`npm run api:types`), so both sides stay in sync.

---

## 🔐 Sign-in and API auth

Only Google sign-in is open to the public. The web app hands the API a short-lived signed token, and the API checks it against the web app's public keys.

```mermaid
sequenceDiagram
    autonumber
    actor U as User
    participant W as Web app (Better Auth)
    participant G as Google
    participant A as API
    participant D as Postgres

    U->>W: Sign in with Google
    W->>G: OAuth
    G-->>W: Profile (name, email)
    W->>D: Save user + session (auth schema)
    U->>W: Open dashboard
    W->>W: GET /api/auth/token → JWT (Ed25519)
    W->>A: GET /v1/me  Authorization: Bearer <JWT>
    A->>W: Fetch JWKS (cached)
    A->>A: Verify signature, issuer, expiry
    A->>D: Upsert profile (app schema)
    A-->>W: Profile
```

- The API never reads the `auth` schema. It trusts only the signed token.
- Config: `AUTH_JWKS_URL` and `AUTH_ISSUER` on the API, `BETTER_AUTH_URL` on the web.

---

## 🎟️ Two kinds of deals

Every campaign has **two** prices. This is the core idea of BackIt.

```mermaid
flowchart LR
    subgraph Founding["🏅 Founding members"]
        direction TB
        F1[Limited spots, e.g. 500]
        F2[Pay once, e.g. $60]
        F3[Get the founding offer<br/>lifetime / months / % off / voucher]
        F4[Get a badge #, access code<br/>and a referral link]
    end
    subgraph Friends["👋 Friends via a referral link"]
        direction TB
        R1[Prepay N months of the<br/>regular plan, e.g. 12 × $12]
        R2[Get a discount, e.g. 20% off<br/>→ pay $115.20 not $144]
        R3[The backer who shared<br/>earns a commission, e.g. $28.80]
    end
    Founding -- "shares link" --> Friends
```

All maths happens on the server in integer cents, with rates in basis points (`money.py`):

```
list        = monthly_price × months
discount    = round_half_up(list × discount_bps / 10000)
amount      = list − discount
commission  = round_half_up(amount × commission_bps / 10000)
platform_fee= round_half_up(amount × 800 / 10000)        # 8%
```

The **AI offer advisor** suggests the founding price, spots, discount and commission, and explains why. It also projects what the builder keeps. The builder can still change every number. The founding price stays a little below what a referred friend pays for the same access (75–95% of it), so founding members get the best deal and the friend link is still worth using.

---

## 💳 Checkout with PayPal

The builder is the merchant of record. BackIt's 8% fee is taken through PayPal's `platform_fees` on the same order.

```mermaid
sequenceDiagram
    autonumber
    actor Buyer
    participant W as Web app
    participant A as API
    participant P as PayPal
    participant D as Postgres

    Buyer->>W: Click "Back it" (or a friend link /{slug}?ref=CODE)
    W->>A: POST /v1/campaigns/{id}/orders {kind, referral_code}<br/>Idempotency-Key
    A->>A: Validate code, block self-referral,<br/>one founding spot per user
    A->>D: Reserve spot for 15 min, save order (created)
    A->>P: Create order (payee = builder merchant_id,<br/>platform_fees = 8%)
    P-->>A: Approval link
    A-->>W: Order
    W->>P: Redirect buyer to PayPal
    Buyer->>P: Approve payment
    P-->>W: Return to /checkout/{orderId}/return
    W->>A: POST /v1/orders/{id}/capture
    A->>P: Capture
    P-->>A: COMPLETED
    A->>D: Order completed · backing (+ badge #) ·<br/>access code · commission (held) · ledger · outbox
    A-->>W: Receipt: badge, access code, share link
    P--)A: Webhook PAYMENT.CAPTURE.COMPLETED (backup path)
```

- If PayPal says "pending", the order becomes `pending_provider` and the webhook finishes it later.
- Unpaid reservations expire, and the worker frees the spot.
- Repeating a request with the same `Idempotency-Key` returns the same result, so a double click can't charge twice.

---

## 💸 Referral rewards: from sale to payout

```mermaid
sequenceDiagram
    autonumber
    actor Friend
    actor Backer
    actor Builder
    participant A as API
    participant K as Worker
    participant AI as AI (OpenRouter)
    participant P as PayPal Payouts

    Friend->>A: Buys through backer's link
    A->>A: Risk rules (same email, same PayPal payer…)
    A->>A: Commission = held, release_at = +30 days
    Note over A,K: 30-day hold covers refund window
    K->>A: Release due holds → payable
    Builder->>A: POST /products/{id}/payout-previews
    A->>A: Group payable rewards per backer,<br/>exclude: below $1, in hold, no payout email,<br/>risk review, refund pending
    A->>AI: Explain this preview + review risk signals
    AI-->>A: Plain-language summary (or template)
    A-->>Builder: Preview: who gets what, who is skipped, why, digest
    Builder->>A: Approve {digest, funding_confirmed}
    A->>A: Digest still matches? (else 409 stale_preview)<br/>Commissions → reserved, batch queued
    K->>P: Create payout batch
    P-->>K: Batch + item statuses
    K->>A: Commissions → submitted → paid · ledger entries
    P--)Backer: 💙 Money in PayPal
```

The builder can also **hold** a single backer from a preview if something looks off.

---

## ↩️ Refunds

```mermaid
flowchart LR
    S[Builder clicks Refund] --> PR[PayPal refund]
    PR --> O[Order → refunded]
    O --> C{Commission state?}
    C -- "held / payable" --> X[Cancel → reversed]
    C -- "paid" --> Y[Reversal ledger entry]
    O --> WH[Webhook refund.issued<br/>to builder's app]
    WH --> REV[Builder's app revokes access]
    O --> AC[Access code stops working<br/>410 access_revoked]
```

Full refunds only. Each refund writes ledger entries, so the public ledger stays honest.

---

## 🔔 Telling the builder's app: webhooks and access codes

BackIt tells the builder's product when someone buys or gets refunded, so access turns on and off automatically.

```mermaid
sequenceDiagram
    autonumber
    participant K as BackIt worker
    participant App as Builder's app
    actor Backer

    K->>K: body = JSON event<br/>sig = hex(HMAC_SHA256(secret, "{ts}.{body}"))
    K->>App: POST /webhooks/backit<br/>BackIt-Event-Id · BackIt-Timestamp<br/>BackIt-Signature: v1=sig · BackIt-Key-Version
    App->>App: Constant-time compare,<br/>timestamp within 5 min,<br/>drop duplicate event ids
    App-->>K: 2xx (else retry with backoff → dead)
    Backer->>App: Enter access code XXXX-XXXX-XXXX
    App->>K: POST /v1/claims/redeem<br/>Bearer = webhook secret
    K-->>App: redeemed · badge # · plan
    App->>App: Unlock Pro for this account
```

- Events: `ping`, `purchase.completed`, `refund.issued`.
- Outgoing URLs go through an **SSRF guard**: no private or local addresses, except `localhost` in development.
- Webhook secrets are encrypted at rest with `APP_ENCRYPTION_KEY` and shown to the builder only once. They can be rotated.
- Builders can see every delivery, and retry it, on the Setup tab.

---

## 🤖 Where AI helps (and where it doesn't)

```mermaid
flowchart LR
    subgraph Uses["AI writes and explains"]
        A1[✍️ Campaign draft<br/>headline · story]
        A2[🧮 Offer advisor<br/>prices · spots · reasons]
        A3[📣 Share drafts<br/>X · LinkedIn · email<br/>with disclosure]
        A4[🧾 Payout explanation]
        A5[🛡️ Risk review<br/>can only raise risk]
    end
    LLM[OpenRouter<br/>JSON schema] --> V{Pydantic<br/>valid?}
    V -- yes --> OK["source: ai"]
    V -- no / timeout / no key --> T["Template fallback<br/>source: template"]
    OK & T --> Uses
```

**Hard limits:**

- 🚫 AI never computes money. Prices and totals always come from `money.py`.
- 🚫 AI never moves money. A human approves every payout.
- 🚫 AI can never rate a backer as **safer** than the rules do. It can only flag more risk and explain.
- 📝 Every call is logged in `ai_runs`.

---

## ⏱️ The worker

One loop, run every minute by Cloud Scheduler (or `--loop` locally). Each step claims rows with `FOR UPDATE SKIP LOCKED` and a lease, so two workers never do the same job.

```mermaid
flowchart TB
    T((⏰ every minute)) --> X[Expire unpaid orders<br/>free reserved spots]
    X --> H[Release 30-day holds<br/>held → payable]
    H --> E[PayPal event inbox<br/>provider_events]
    E --> J[Outbox jobs<br/>execute_payout · retry pending batches]
    J --> W[Builder webhook deliveries]
    W --> M[Emails via Resend]
```

Failed jobs retry with exponential backoff, then become `dead` and show up in the UI.

---

## 🔄 State machines

### Order

```mermaid
stateDiagram-v2
    [*] --> created: POST /orders
    created --> completed: capture OK
    created --> pending_provider: PayPal pending
    pending_provider --> completed: webhook
    pending_provider --> failed: denied
    created --> cancelled: buyer cancels / expires
    created --> failed: capture error
    completed --> refunded: builder refunds
    refunded --> [*]
```

### Commission (backer's reward)

```mermaid
stateDiagram-v2
    [*] --> held: referral sale
    [*] --> blocked: risk rule hit
    blocked --> held: builder clears flag
    held --> payable: 30 days pass
    payable --> reserved: payout approved
    reserved --> submitted: sent to PayPal
    submitted --> paid: PayPal success
    submitted --> payable: failed / returned
    held --> reversed: refund
    payable --> reversed: refund
    paid --> [*]
    reversed --> [*]
```

### Payout preview and batch

```mermaid
stateDiagram-v2
    direction LR
    state Preview {
        [*] --> open
        open --> approved: digest matches
        open --> stale: data changed
        open --> expired: too old
    }
    state Batch {
        [*] --> queued
        queued --> submitted
        submitted --> processing
        processing --> success
        processing --> partial
        processing --> failed
    }
    approved --> queued
```

### Campaign

```mermaid
stateDiagram-v2
    direction LR
    [*] --> draft
    draft --> published: readiness checks pass
    published --> closed: builder ends it
```

Readiness checks before publishing: PayPal connected, revenue verified (3 months of at least $100), webhook URL set, valid prices and rates, and a free campaign URL.

---

## 🗄️ Data model

Main tables in the `app` schema (IDs are prefixed strings like `prd_`, `cmp_`, `ord_`, `bck_`, `com_`):

```mermaid
erDiagram
    PROFILE ||--o{ PRODUCT : owns
    PRODUCT ||--o| SELLER_CONNECTION : "PayPal merchant"
    PRODUCT ||--o{ REVENUE_VERIFICATION : proves
    PRODUCT ||--o| CAMPAIGN : runs
    CAMPAIGN ||--o{ ORDER : sells
    PROFILE ||--o{ ORDER : buys
    ORDER ||--o| BACKING : creates
    CAMPAIGN ||--o{ BACKING : has
    PROFILE ||--o{ BACKING : holds
    ORDER ||--o| COMMISSION : "referral earns"
    BACKING ||--o{ COMMISSION : "is owed"
    ORDER ||--o| REFUND : "may get"
    PRODUCT ||--o{ PAYOUT_PREVIEW : drafts
    PAYOUT_PREVIEW ||--o| PAYOUT_BATCH : "approved as"
    PAYOUT_BATCH ||--o{ PAYOUT_ITEM : contains
    PAYOUT_ITEM ||--o{ PAYOUT_ALLOCATION : covers
    COMMISSION ||--o{ PAYOUT_ALLOCATION : "paid by"
    PRODUCT ||--o{ WEBHOOK_DELIVERY : sends
    PRODUCT ||--o{ RISK_FLAG : raises
    BACKING ||--o{ ACCESS_REPORT : files
    CAMPAIGN ||--o{ LEDGER_ENTRY : records

    CAMPAIGN {
        string slug
        string status
        int founding_price_cents
        int founding_spots_cap
        int referral_list_price_cents
        int referral_months
        int referral_discount_bps
        int commission_bps
        int platform_fee_bps
    }
    ORDER {
        string kind "founding | referral"
        string state
        int amount_cents
        int platform_fee_cents
        int commission_cents
        string paypal_order_id
    }
    BACKING {
        int badge_number
        string referral_code
        string claim_code
    }
    COMMISSION {
        string state
        int amount_cents
        datetime release_at
    }
```

Supporting tables: `provider_events` (PayPal inbox), `outbox_jobs`, `idempotency_keys`, `ai_runs`, `audit_events` and `notifications`.

---

## ☁️ Deployment

```mermaid
flowchart LR
    DEV([💻 git push / gcloud deploy])
    subgraph Vercel
        BUILD[npm run build<br/>prebuild: fetch-fonts.mjs]
        BLOB[(Private Blob<br/>Timeless fonts)]
        WEBP[backit.club]
    end
    subgraph GCP["GCP · backit-512304 · us-central1"]
        RUN[Cloud Run service<br/>backit-api]
        JOB[Cloud Run job<br/>backit-worker --once]
        SCH[Cloud Scheduler<br/>every minute]
        TEST[Cloud Run<br/>backit-test-app<br/>min=max=1, SQLite]
        SEC[[Secret Manager]]
        PG[(Postgres)]
    end
    DEV --> BUILD
    BLOB --> BUILD --> WEBP
    DEV --> RUN & JOB & TEST
    SCH --> JOB
    SEC -.-> RUN & JOB & TEST
    RUN & JOB --> PG
    WEBP --> PG
```

| Host | Domain |
|---|---|
| Web | `https://backit.club` |
| API | `https://api.backit.club` (PayPal webhook: `/v1/webhooks/paypal`) |
| Demo product | `https://test-app.backit.club` |

The fonts are licensed and can't be public, so they're fetched from a private Vercel Blob store at build time and are never committed.

---

## 🛡️ Safety rules we never break

| Rule | How |
|---|---|
| 💰 No floating-point money | Integer cents, basis points, half-up rounding in one place (`money.py`) |
| 🔁 No double charges or payouts | `Idempotency-Key` on money POSTs, unique DB constraints, digest check on payout approval |
| 📒 Every cent is traceable | Append-only `ledger_entries`, plus a public ledger per campaign |
| ⏳ Rewards wait for refunds | 30-day hold, $1 minimum payout |
| 🧍 A human approves money out | Payout preview → explicit approve |
| 🕵️ Fraud checks | Rule-based risk flags (self-referral, shared payer, bursts, new accounts), with AI only able to escalate |
| 🔐 Secrets stay secret | Secret Manager in prod, encrypted webhook secrets, keys never in the repo |
| 🌐 Safe outgoing calls | SSRF guard and HMAC-signed builder webhooks |
| 🧪 Sandbox only | `PAYPAL_MODE` is `mock` or `sandbox`; live PayPal endpoints are never called |
| ⚖️ Not an investment | Backers buy a product deal, not equity or profit share |
