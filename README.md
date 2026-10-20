# BackIt

**backit.club** lets builders run founding-backer campaigns. Backers pre-buy through PayPal checkout, get a permanent founding badge and a referral link, and earn commissions on referred sales. BackIt notifies the builder's app by signed webhook so product access is real. An AI agent drafts campaign copy, share posts, and payout previews, and a human approves every payout.

Backing is a purchase, not an investment. There is no equity and no revenue share.

## Repository

| Path | What |
|---|---|
| `apps/web` | Next.js 16 app with shadcn/ui, Tailwind v4, and Better Auth (JWT). Contains the builder workspace, backer pages, public campaign and checkout. |
| `services/api` | FastAPI API and worker (outbox, webhooks, holds, payouts). See [its README](services/api/README.md). |
| `examples/demo-product` | A stand-in builder product that receives signed BackIt webhooks and grants or revokes access. |
| `docs/api-contract.md` | The HTTP contract, which is the source of truth for both sides. |
| `PRODUCT.md`, `DESIGN.md` | Product context and design system. |

## Prerequisites

- Postgres 16
- [uv](https://docs.astral.sh/uv/)
- Node 24
- The Timeless Sans variable font (`TimelessSansVF.ttf`). Its license forbids redistribution, so it is gitignored. Copy your licensed file to `apps/web/src/fonts/TimelessSansVF.ttf` before building.

## Local setup

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

### Google sign-in

Sign-in and sign-up use Google only. To create the keys:

1. Open [Google Cloud Console → Credentials](https://console.cloud.google.com/apis/credentials) and create an **OAuth client ID** of type **Web application**.
2. Add `http://localhost:3000` as an authorized JavaScript origin, and `http://localhost:3000/api/auth/callback/google` as an authorized redirect URI.
3. Put the client ID and secret in `apps/web/.env.local` as `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, then restart `npm run dev`.

The first Google sign-in creates the account, using the Google name and email.

### Demo product (terminal 4)

The demo product verifies webhook signatures, so it needs the secret that BackIt shows **once** when you create a product. Follow this order:

1. Sign in with Google at `http://localhost:3000`. Then go to **Campaigns → Add a product** (`/app/products/new`) and set the webhook URL to `http://localhost:8100/webhooks/backit`.
2. Copy the `whsec_…` secret shown after creation. If you lose it, rotate it in Setup.
3. Start the demo product:
   ```bash
   cd examples/demo-product
   BACKIT_WEBHOOK_SECRET=whsec_... uv run fastapi dev --port 8100
   ```
4. In **Setup**, click **Send test ping**. It should show as delivered.

## Mock walkthrough

With `PAYPAL_MODE=mock`, the whole loop runs locally. Every mock ID is prefixed `MOCK` and labelled in the UI.

1. **Builder:** create the product, then complete Setup. Setup covers connecting PayPal (mock), adding revenue evidence (demo), and sending a test ping.
2. **Campaign:** generate an AI draft, edit it, run the readiness check, and publish.
3. **Founding backer:** open `/{slug}` in another browser, sign up, and buy. The badge appears and `/demo` shows access granted.
4. **Referral sale:** copy the backer's link from **Backing**, open it in a third account, and buy. The discount applies, and the backer's commission appears as *held*.
5. **Refund:** refund a sale in **Sales**. The demo product revokes access and the commission is reversed.
6. **Payout:** the backer sets a payout email in Settings. In development, use **Skip hold (demo)** on Payouts. Then create a preview, review the agent summary and exclusions, and approve.

## Environment

The defaults run in mock mode. Set these for sandbox and production paths:

| Variable | Where | Purpose |
|---|---|---|
| `PAYPAL_MODE=sandbox`, `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_WEBHOOK_ID` | `services/api/.env` | PayPal sandbox Orders, Partner Referrals, Payouts, and webhook verification |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | `services/api/.env` | AI drafts. Without them, the API falls back to templates. |
| `APP_ENCRYPTION_KEY` | `services/api/.env` | Encrypts webhook secrets at rest |
| `AUTH_JWKS_URL`, `AUTH_ISSUER` | `services/api/.env` | Verifies Better Auth JWTs |
| `BETTER_AUTH_SECRET`, `BETTER_AUTH_URL`, `AUTH_DATABASE_URL` | `apps/web/.env.local` | Auth |
| `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_DEMO_PRODUCT_URL` | `apps/web/.env.local` | API and demo product URLs |

## Checks

```bash
cd services/api && uv run pytest && uv run ruff check .
cd examples/demo-product && uv run pytest
cd apps/web && npm run lint && npx tsc --noEmit && npm run build
```
