from fastapi.testclient import TestClient

from tests.conftest import make_token


def test_requires_bearer_token(client: TestClient) -> None:
    r = client.get("/v1/me")
    assert r.status_code == 401
    body = r.json()["error"]
    assert body["code"] == "unauthorized"
    assert body["request_id"].startswith("req_")
    assert r.headers["X-Request-ID"] == body["request_id"]


def test_rejects_wrong_audience_and_expired(client: TestClient) -> None:
    bad_aud = make_token("u1", "u1@example.com", "U1", aud="http://evil.example")
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {bad_aud}"}).status_code == 401
    expired = make_token("u1", "u1@example.com", "U1", exp=1)
    assert client.get("/v1/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_upserts_profile(client: TestClient, auth) -> None:
    r = client.get("/v1/me", headers=auth("alice", "alice@example.com", "Alice"))
    assert r.status_code == 200
    assert r.json()["profile"] == {"id": "alice", "email": "alice@example.com", "display_name": "Alice",
                                   "payout_email": None, "payout_email_verified": False}


def test_config_is_public(client: TestClient) -> None:
    r = client.get("/v1/config")
    assert r.json() == {"paypal_mode": "mock", "paypal_client_id": None, "ai_enabled": False,
                        "platform_fee_bps": 800, "hold_days": 30, "payout_minimum_cents": 100,
                        "environment": "development"}
