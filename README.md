# BackIt

**Turn your product's first fans into your best salespeople.**

- 🌐 **Live site:** [backit.club](https://backit.club)
- 🎬 **Demo video:** [Watch on YouTube](https://www.youtube.com/watch?v=lSgo9OTiL-g)

---

## 💡 What is BackIt?

You built something people love, but getting your first paying customers is hard. Ads cost too much 💸 and big discounts eat your profit 📉.

BackIt fixes that by letting your earliest fans help you grow:

- 🏷️ **You set up a founding offer.** AI helps you pick a fair price and writes your campaign page.
- 🙌 **Fans back it early.** They pay once with PayPal, get a special founding price and a numbered badge.
- 🔗 **They share it with friends.** Friends get a discount, and the backer earns a reward for every sale.
- 💰 **Backers get paid.** An AI agent prepares the payouts, you approve them, and PayPal Payouts sends the money.

> 🙅 Backing is a purchase, not an investment. There's no equity and no revenue share.

## 🧪 Try it yourself (for judges)

Everything runs on the PayPal **sandbox**, so no real money moves. The demo logins (two BackIt accounts and a PayPal sandbox buyer) are in the hackathon submission. You can also sign in with your own Google account.

1. 🛒 **Back a product.** Open [backit.club/ledgerly](https://backit.club/ledgerly), click **Claim a founding spot**, and sign in with the demo **backer** account (Sign in → *Use a demo account*).
2. 💳 **Pay with PayPal.** Log in with the sandbox buyer. Confetti 🎉 means the payment went through.
3. 🔓 **Unlock the product.** Copy the access code from the success screen, open [test-app.backit.club](https://test-app.backit.club) (Ledgerly, a pretend app with a paywall), and paste it in to unlock Pro.
4. 📣 **Share your link.** In your dashboard, copy your referral link. Open it in a private window and buy with another account to see the friend discount. The first backer earns a reward.
5. 📊 **See the builder side.** Sign out and sign in with the demo **builder** account to see sales, notifications, campaign stats, payouts and refunds.

Ledgerly has 500 founding spots, so there's plenty of room to play around. 😄

To recreate the demo accounts on another database: `DEMO_BUILDER_PASSWORD=… DEMO_BACKER_PASSWORD=… node --env-file=.env.local scripts/create-demo-users.mjs` (run it from `apps/web`). Email/password sign-up is turned off; only these seeded accounts can sign in that way.

## 🛠️ Built with

- ⚛️ **Next.js 16**, shadcn/ui and Tailwind for the web app
- ⚡ **FastAPI** and Postgres for the API
- 💙 **PayPal** Checkout and PayPal Payouts for money in and money out
- 🤖 **AI** for offer suggestions, campaign writing and payout previews

## 📁 Repository

| Path | What |
|---|---|
| `apps/web` | Next.js 16 app with shadcn/ui, Tailwind v4, and Better Auth (JWT). Contains the builder workspace, backer pages, public campaign and checkout. |
| `services/api` | FastAPI API and worker (outbox, webhooks, holds, payouts). See [its README](services/api/README.md). |
| `examples/demo-product` | A stand-in builder product that receives signed BackIt webhooks and grants or revokes access. |
| `docs/api-contract.md` | The HTTP contract, which is the source of truth for both sides. |
| `PRODUCT.md`, `DESIGN.md` | Product context and design system. |

## ✅ Prerequisites

- Postgres 16
- [uv](https://docs.astral.sh/uv/)
- Node 24
- The Timeless fonts (`TimelessSerifVF.ttf`, `TimelessSerifItalicVF.ttf`, `TimelessSansVF.ttf`). Their license forbids public repos, so they are gitignored. Locally, copy them into `apps/web/src/fonts/`. On Vercel, `npm run build` runs `scripts/fetch-fonts.mjs` first, which downloads any missing font from a private Vercel Blob store using `FONTS_BASE_URL` and `BLOB_READ_WRITE_TOKEN`.

## 🚀 Local setup

```bash
# 1. Database
createdb backit
psql backit -c 'create schema if not exists auth; create schema if not exists app;'

# 2. API (terminal 1). Mock PayPal and template AI work without any keys.
cd services/api
cp .env.example .env
uv sync
uv run alembic upgrade head
uv run fastapi dev                                   # http://localhost:8000/docs

# 3. Worker (terminal 2)
cd services/api && uv run python -m app.workers.run --loop

# 4. Web (terminal 3)
cd apps/web
cp .env.example .env.local                           # set BETTER_AUTH_SECRET and Google OAuth keys
npm install
npx @better-auth/cli@latest migrate --config src/lib/auth.ts -y
npm run dev                                          # http://localhost:3000
```

### 🔑 Google sign-in

Sign-in and sign-up use Google only. To create the keys:

1. Open [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials) and create an **OAuth client ID** of type **Web application**.
2. Add `http://localhost:3000` as an authorized JavaScript origin, and `http://localhost:3000/api/auth/callback/google` as an authorized redirect URI.
3. Put the client ID and secret in `apps/web/.env.local` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, then restart `npm run dev`.

The first Google sign-in creates the account, using the Google name and email.

### 🧩 Demo product (terminal 4)

The demo product verifies webhook signatures, so it needs the secret that BackIt shows **once** when you create a product. Follow this order:

1. Sign in with Google at `http://localhost:3000`. Then go to **Campaigns → Add a product** (`/app/products/new`) and set the webhook URL to `http://localhost:8100/webhooks/backit`.
2. Copy the `whsec_…` secret shown after creation. If you lose it, rotate it in Setup.
3. Start the demo product:
   ```bash
   cd examples/demo-product
   BACKIT_WEBHOOK_SECRET=whsec_... BACKIT_PRODUCT_ID=prd_... uv run fastapi dev --port 8100
   ```
4. In **Setup**, click **Send test ping**. It should show as delivered.

`BACKIT_PRODUCT_ID` (and `BACKIT_API_URL`, default `http://localhost:8001`) let `/demo` redeem backers' one-time access codes. See [Access claim codes](docs/api-contract.md#access-claim-codes).

## 🎭 Mock walkthrough

With `PAYPAL_MODE=mock`, the whole loop runs locally. Every mock ID is prefixed `MOCK` and labelled in the UI.

1. **Builder:** create the product, then complete Setup. Setup covers connecting PayPal (mock), adding revenue evidence (demo), and sending a test ping.
2. **Campaign:** generate an AI draft, edit it, run the readiness check, and publish.
3. **Founding backer:** open `/{slug}` in another browser, sign up, and buy. The badge and a one-time access code appear. Redeem the code on `/demo` to unlock it for an account there.
4. **Referral sale:** copy the backer's link from **Backing**, open it in a third account, and buy. The discount applies, and the backer's commission appears as *held*.
5. **Refund:** refund a sale in **Sales**. The demo product revokes access, the code stops working, and the commission is reversed.
6. **Payout:** the backer sets a payout email in Settings. In development, use **Skip hold (demo)** on Payouts. Then create a preview, review the agent summary and exclusions, and approve.

## ⚙️ Environment

The defaults run in mock mode. Set these for sandbox and production paths:

| Variable | Where | Purpose |
|---|---|---|
| `PAYPAL_MODE=sandbox`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID` | `services/api/.env` | PayPal sandbox Orders, Partner Referrals, Payouts, and webhook verification |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | `services/api/.env` | AI drafts. Without them, the API falls back to templates. |
| `APP_ENCRYPTION_KEY` | `services/api/.env` | Encrypts webhook secrets at rest |
| `AUTH_JWKS_URL`, `AUTH_ISSUER` | `services/api/.env` | Verifies Better Auth JWTs |
| `DB_SERVER`, `DB_USERNAME`, `DB_PASSWORD`, `DB_NAME` | `services/api/.env` and `apps/web/.env.local` | Shared Postgres for app data and auth (`DB_SERVER` is `host` or `host:port`) |
| `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL` | `apps/web/.env.local` | Auth |
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEMO_PRODUCT_URL` | `apps/web/.env.local` | API and demo product URLs |

## 🧹 Checks

```bash
cd services/api && uv run pytest && uv run ruff check .
cd examples/demo-product && uv run pytest
cd apps/web && npm run lint && npx tsc --noEmit && npm run build
```
