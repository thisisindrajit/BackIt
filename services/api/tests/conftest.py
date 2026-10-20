import os

# Configure the app for tests BEFORE any app module is imported.
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://indrajit@localhost:5432/backit_test"
)
os.environ["ENVIRONMENT"] = "development"
os.environ["PAYPAL_MODE"] = "mock"
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["AUTH_ISSUER"] = "http://localhost:3000"
os.environ["WEB_BASE_URL"] = "http://localhost:3000"

import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import jwt
import pytest
from alembic import command
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fastapi.testclient import TestClient
from sqlalchemy import text

from app import webhooks_out
from app.auth import get_key_source
from app.db import SessionLocal, engine
from app.main import app

ROOT = Path(__file__).resolve().parents[1]
ISSUER = "http://localhost:3000"
PRIVATE_KEY = Ed25519PrivateKey.generate()


class _Key:
    def __init__(self, key: Any) -> None:
        self.key = key


class FakeKeySource:
    """Stands in for PyJWKClient: returns the test Ed25519 public key."""

    def get_signing_key_from_jwt(self, token: str) -> _Key:
        return _Key(PRIVATE_KEY.public_key())


def make_token(sub: str, email: str, name: str, **overrides: Any) -> str:
    now = int(time.time())
    claims = {"sub": sub, "email": email, "name": name, "iss": ISSUER, "aud": ISSUER,
              "iat": now, "exp": now + 600, **overrides}
    return jwt.encode(claims, PRIVATE_KEY, algorithm="EdDSA")


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS app CASCADE"))
        conn.execute(text("CREATE SCHEMA app"))
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    cfg.attributes["configure_logger"] = False
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def _clean() -> Iterator[None]:
    yield
    with engine.begin() as conn:
        tables = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'app' AND tablename <> 'alembic_version'"
        )).scalars().all()
        conn.execute(text("TRUNCATE " + ", ".join(f"app.{t}" for t in tables) + " CASCADE"))


@pytest.fixture
def sent_webhooks(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Capture outgoing builder webhooks instead of hitting the network."""
    sent: list[dict[str, Any]] = []

    def fake_send(url: str, secret: str, key_version: int, event_id: str,
                  payload: dict[str, Any]) -> webhooks_out.AttemptResult:
        body = webhooks_out.serialize_body(payload)
        ts = int(time.time())
        sent.append({"url": url, "secret": secret, "event_id": event_id, "payload": payload,
                     "body": body, "timestamp": ts, "signature": webhooks_out.sign(secret, ts, body)})
        return webhooks_out.AttemptResult(True, 200, None, "ok")

    monkeypatch.setattr(webhooks_out, "send", fake_send)
    return sent


@pytest.fixture
def client(sent_webhooks: list[dict[str, Any]]) -> Iterator[TestClient]:
    app.dependency_overrides[get_key_source] = FakeKeySource
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def db() -> Iterator[Any]:
    with SessionLocal() as session:
        yield session


@pytest.fixture
def auth() -> Callable[..., dict[str, str]]:
    def _auth(sub: str, email: str | None = None, name: str | None = None) -> dict[str, str]:
        email = email or f"{sub}@example.com"
        return {"Authorization": f"Bearer {make_token(sub, email, name or sub.title())}"}

    return _auth


OFFER = {
    "founding_price_cents": 4900,
    "founding_spots_cap": 3,
    "referral_list_price_cents": 10000,
    "referral_discount_bps": 2000,
    "commission_bps": 2500,
}


@pytest.fixture
def campaign(client: TestClient, auth: Callable[..., dict[str, str]]) -> dict[str, Any]:
    """A published campaign owned by `builder` with a mock-connected seller."""
    h = auth("builder", "builder@example.com", "Bea Builder")
    r = client.post("/v1/products", headers=h, json={
        "name": "Shipfast", "url": "https://shipfast.example.com",
        "description": "Ship SaaS quickly", "access_terms": "Lifetime access to Pro",
        "refund_terms": "30-day refunds", "webhook_url": "http://localhost:8100/webhooks/backit",
    })
    assert r.status_code == 201, r.text
    product = r.json()
    assert client.post(f"/v1/products/{product['id']}/paypal/onboarding", headers=h).json()["status"] == "connected"
    r = client.post(f"/v1/products/{product['id']}/verification/demo", headers=h,
                    json={"months": [150000, 120000, 110000]})
    assert r.json()["threshold_met"] is True
    r = client.post("/v1/campaigns", headers=h, json={
        "product_id": product["id"], "slug": "shipfast", "headline": "Back Shipfast",
        "summary": "Founding access", "story": "We build tools.", **OFFER,
    })
    assert r.status_code == 201, r.text
    cmp = r.json()
    r = client.post(f"/v1/campaigns/{cmp['id']}/publish", headers=h)
    assert r.status_code == 200, r.text
    return {"product": product, "campaign": r.json(), "headers": h,
            "secret": product["webhook_secret"]}


@pytest.fixture
def buy(client: TestClient, auth: Callable[..., dict[str, str]]) -> Callable[..., dict[str, Any]]:
    def _buy(campaign_id: str, sub: str, kind: str = "founding", code: str | None = None,
             email: str | None = None) -> dict[str, Any]:
        h = auth(sub, email)
        body: dict[str, Any] = {"kind": kind}
        if code:
            body["referral_code"] = code
        r = client.post(f"/v1/campaigns/{campaign_id}/orders", headers=h, json=body)
        assert r.status_code == 201, r.text
        r = client.post(f"/v1/orders/{r.json()['id']}/capture", headers=h)
        assert r.status_code == 200, r.text
        return r.json()

    return _buy
