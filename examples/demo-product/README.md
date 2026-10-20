# BackIt demo product

A tiny stand-in for a builder's product. It receives signed BackIt webhooks and keeps entitlements in a local SQLite file (`demo.sqlite3`, or `DEMO_DB_PATH`).

```bash
cd examples/demo-product
export BACKIT_WEBHOOK_SECRET=whsec_...   # from POST /v1/products (or rotate)
uv run fastapi dev --port 8100
```

Set the product's webhook URL in BackIt to `http://localhost:8100/webhooks/backit`. Plain http to localhost is accepted only when the API runs with `ENVIRONMENT=development`.

- `POST /webhooks/backit` checks `BackIt-Signature`, which is `v1=hex(hmac_sha256(secret, "{BackIt-Timestamp}.{raw_body}"))`. The comparison is constant-time, timestamps must be within 5 minutes, and duplicate event ids are dropped. It grants access on `purchase.completed`, revokes only that order on `refund.issued`, and answers `ping`.
- `GET /entitlements` returns `[{order_id, buyer_email, plan_id, status, granted_at, revoked_at}]`.
- `GET /events` returns recently processed events.
- CORS allows `http://localhost:3000` (override with `CORS_ORIGINS`).

Tests: `uv run pytest`. Lint: `uv run ruff check .`
