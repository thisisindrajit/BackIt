# BackIt API

FastAPI backend for BackIt: founding-backer campaigns with referral commissions on PayPal.
The HTTP contract is in [`docs/api-contract.md`](../../docs/api-contract.md); every route lives under `/v1`.

## Local setup

Requirements: uv, and a local Postgres 16 with database `backit` and schemas `app` (BackIt) and `auth` (Better Auth). BackIt never touches `auth`.

```bash
cd services/api
cp .env.example .env          # defaults work locally: PAYPAL_MODE=mock, template AI
uv sync
uv run alembic upgrade head   # creates all tables in schema "app" (version table app.alembic_version)
uv run fastapi dev            # http://localhost:8000  (docs at /docs)
uv run python -m app.workers.run --loop   # second terminal: outbox, webhooks, payouts, holds
```

`python -m app.workers.run --once` drains one round of work and exits.

## Tests and lint

```bash
createdb backit_test          # once; tests recreate the app schema via Alembic
uv run pytest
uv run ruff check .
```

Tests sign their own EdDSA JWTs through a dependency override and capture outgoing webhooks, so no network access is needed.
Set `TEST_DB_SERVER`, `TEST_DB_USERNAME`, `TEST_DB_PASSWORD` or `TEST_DB_NAME` to use a different test database.

## Modes

- **PayPal** — `PAYPAL_MODE=mock` (default) runs checkout, refunds, onboarding and payouts locally. Mock IDs are prefixed `MOCK` and `provider` is `"mock"`. `PAYPAL_MODE=sandbox` with `PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET` and `PAYPAL_WEBHOOK_ID` uses `https://api-m.sandbox.paypal.com`: Orders v2 with `platform_fees` and builder `payee.merchant_id`, Partner Referrals, webhook signature verification, and Payouts. Live endpoints are never called.
- **AI** — with `OPENROUTER_API_KEY`, campaign drafts, share drafts and payout explanations call OpenRouter with JSON-schema output. Output is validated with Pydantic. On any failure the response falls back to a template (`source: "template"`). AI never computes money.
- **Mock PayPal webhooks** — in development only, `POST /v1/webhooks/paypal` accepts events with the header `paypal-transmission-sig: mock`.

## Layout

```
app/main.py          app factory, CORS, request-id middleware, error envelope
app/config.py        settings (pydantic-settings, .env)
app/auth.py          Better Auth JWT (JWKS) verification + profile upsert
app/models.py        SQLAlchemy models + DB constraints (schema "app")
app/money.py         integer-cents pricing, half-up rounding
app/routers/         HTTP routes (/v1/...)
app/services/        checkout/finalize, refunds, payouts, risk, ledger, sharing, provider events
app/providers/       paypal.py (mock + sandbox), ai.py (OpenRouter + template)
app/webhooks_out.py  builder webhooks: HMAC signing, SSRF guard, delivery
app/workers/run.py   worker: outbox jobs, deliveries, inbox, payouts, holds, order expiry
migrations/          Alembic
```

## Docker

```bash
docker build -t backit-api .
docker run -p 8000:8000 --env-file .env backit-api                        # API
docker run --env-file .env backit-api python -m app.workers.run --loop    # worker
docker run --env-file .env backit-api alembic upgrade head                # migrations
```
