# ⚡ BackIt API

The FastAPI backend behind BackIt. It owns every rule about money: pricing, checkout, refunds, 30-day holds, payouts, risk checks and the public ledger. A worker handles the slow, retryable jobs.

- 📜 **API contract:** [`docs/api-contract.md`](../../docs/api-contract.md). Every route lives under `/v1`.
- 🏗️ **Architecture and diagrams:** [`docs/architecture.md`](../../docs/architecture.md)
- 🌍 **Live:** `https://api.backit.club`

## 🚀 Local setup

You need uv, and a local Postgres 16 with database `backit` and schemas `app` (BackIt) and `auth` (Better Auth). BackIt never touches `auth`.

```bash
cd services/api
cp .env.example .env          # defaults work locally: PAYPAL_MODE=mock, template AI
uv sync
uv run alembic upgrade head   # creates all tables in schema "app" (version table app.alembic_version)
uv run fastapi dev            # http://localhost:8000  (docs at /docs)
uv run python -m app.workers.run --loop   # second terminal: outbox, webhooks, payouts, holds
```

`python -m app.workers.run --once` drains one round of work and exits.

### 🌱 Demo data

Sign in to the web app once, then seed through the real API flows (PayPal mock, development only):

```bash
uv run python scripts/seed_demo.py --owner-email you@example.com          # --reset wipes app data first
```

You get:

- 📒 **Ledgerly**: live, with sales, a refund, a paid payout and held rewards
- 📝 **Shipnote**: a draft campaign
- 🧱 **Pagecraft**: no campaign yet
- 🏅 Backings in two `demo_*` builders' campaigns

Seeded activity is spread over the past ten weeks so the dashboard chart has history; run `uv run python scripts/seed_demo.py --backdate` to do that for data seeded before this existed.

## 🧪 Tests and lint

```bash
createdb backit_test          # once; tests recreate the app schema via Alembic
uv run pytest
uv run ruff check .
```

Tests sign their own EdDSA JWTs through a dependency override and capture outgoing webhooks, so no network access is needed.
Set `TEST_DB_SERVER`, `TEST_DB_USERNAME`, `TEST_DB_PASSWORD` or `TEST_DB_NAME` to use a different test database.

## 🎛️ Modes

- 💙 **PayPal:** `PAYPAL_MODE=mock` (default) runs checkout, refunds, onboarding and payouts locally. Mock IDs are prefixed `MOCK` and `provider` is `"mock"`. `PAYPAL_MODE=sandbox` with `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` and `PAYPAL_WEBHOOK_ID` uses `https://api-m.sandbox.paypal.com`: Orders v2 with `platform_fees` and builder `payee.merchant_id`, Partner Referrals, webhook signature verification, and Payouts. Live endpoints are never called.
- 🤖 **AI:** with `OPENROUTER_API_KEY`, campaign drafts, the offer advisor, share drafts, payout explanations and the payout risk review call OpenRouter with JSON-schema output. Output is validated with Pydantic. On any failure the response falls back to a template (`source: "template"`). AI never computes or moves money, and it can only raise a risk level, never lower it.
- 🪝 **Mock PayPal webhooks:** in development only, `POST /v1/webhooks/paypal` accepts events with the header `paypal-transmission-sig: mock`.

### 🏖️ Local PayPal sandbox

Create a **Platform** app in PayPal's sandbox Apps & Credentials. Enable Payouts,
onboarding before payment, and platform fees. Keep its client ID and secret in the
ignored `services/api/.env`, together with `PAYPAL_PARTNER_MERCHANT_ID` (the platform
sandbox business account's Account ID) and `PAYPAL_BN_CODE`.

For local ports 3001 (web) and 8001 (API), set `WEB_BASE_URL`, `CORS_ORIGINS`, and
`AUTH_ISSUER` to `http://localhost:3001`, and `AUTH_JWKS_URL` to
`http://localhost:3001/api/auth/jwks`. The web app's `BETTER_AUTH_URL` must match;
`NEXT_PUBLIC_API_URL` should be `http://localhost:8001/v1`.

Run `ngrok http http://localhost:8001` and register
`https://<your-ngrok-host>/v1/webhooks/paypal` on the sandbox app. Subscribe to capture
completed/denied/refunded/reversed, payout batch/item events, merchant onboarding
completed, and partner consent revoked. Save the resulting `PAYPAL_WEBHOOK_ID`,
set `PAYPAL_MODE=sandbox`, and restart the API and any worker processes.
Keep the tunnel running while testing; update the webhook if its hostname changes.

Mock demo sellers and transactions are not real sandbox records. Use a new product
and **Connect PayPal** to onboard a sandbox seller, then **Refresh status** after
returning to its Setup tab. Use a separate sandbox Personal account as the buyer.
Do not use mock orders to test sandbox refunds or payouts.

## 📁 Layout

```
app/main.py          app factory, CORS, request-id middleware, error envelope
app/config.py        settings (pydantic-settings, .env)
app/auth.py          Better Auth JWT (JWKS) verification + profile upsert
app/models.py        SQLAlchemy models + DB constraints (schema "app")
app/money.py         integer-cents pricing, half-up rounding
app/routers/         HTTP routes (/v1/...)
app/services/        checkout/finalize, refunds, payouts, risk + AI risk review, ledger, offers,
                     campaigns, sharing, claims, notifications, access reports, provider events
app/providers/       paypal.py (mock + sandbox), ai.py (OpenRouter + template)
app/webhooks_out.py  builder webhooks: HMAC signing, SSRF guard, delivery
app/email.py         notification emails through Resend (skipped without RESEND_API_KEY)
app/workers/run.py   worker: order expiry, holds, PayPal inbox, outbox jobs, deliveries, emails
migrations/          Alembic
```

## 🐳 Docker

```bash
docker build -t backit-api .
docker run -p 8000:8000 --env-file .env backit-api                        # API
docker run --env-file .env backit-api python -m app.workers.run --loop    # worker
docker run --env-file .env backit-api alembic upgrade head                # migrations
```

## ☁️ Production (Google Cloud Run)

Project `backit-512304`, region `us-central1`. `.gcloudignore` keeps `.env` out of the build upload.

- **API:** Cloud Run service `backit-api`, mapped to `https://api.backit.club` (CNAME `api` → `ghs.googlehosted.com.`).
- **Worker:** Cloud Run job `backit-worker` (`python -m app.workers.run --once`), triggered every minute by Cloud Scheduler job `backit-worker-every-minute`.
- **Secrets (Secret Manager):** `db-username`, `db-password`, `app-encryption-key`, `paypal-client-id`, `paypal-client-secret`, `paypal-webhook-id`, `openrouter-api-key` (AI features fall back to templates without it).
- **PayPal webhook:** `https://api.backit.club/v1/webhooks/paypal` on the sandbox app.

🔁 Redeploy after code changes:

```bash
gcloud run deploy backit-api --source . --region us-central1 --project backit-512304
IMG=$(gcloud run services describe backit-api --region us-central1 --project backit-512304 --format='value(spec.template.spec.containers[0].image)')
gcloud run jobs update backit-worker --image "$IMG" --region us-central1 --project backit-512304
```

Env vars and secret bindings persist across deploys; change them with `--update-env-vars` / `--update-secrets`.
