import json
import time
from typing import Any

import pytest

from app.webhooks_out import UnsafeDestination, sign, validate_destination, verify_signature


def test_hmac_sign_and_verify() -> None:
    body = b'{"type":"ping"}'
    ts = int(time.time())
    sig = sign("whsec_test", ts, body)
    assert sig.startswith("v1=")
    assert verify_signature("whsec_test", str(ts), body, sig)
    assert not verify_signature("whsec_other", str(ts), body, sig)
    assert not verify_signature("whsec_test", str(ts), body + b" ", sig)
    assert not verify_signature("whsec_test", str(ts - 301), body, sign("whsec_test", ts - 301, body))
    assert not verify_signature("whsec_test", "not-a-number", body, sig)


def test_purchase_webhook_is_signed_with_product_secret(campaign, buy, sent_webhooks) -> None:
    buy(campaign["campaign"]["id"], "alice")
    event = next(w for w in sent_webhooks if w["payload"]["type"] == "purchase.completed")
    assert event["secret"] == campaign["secret"]
    assert verify_signature(campaign["secret"], str(event["timestamp"]), event["body"], event["signature"])
    data = event["payload"]["data"]
    assert data["buyer_email"] == "alice@example.com"  # builders need the email to grant access
    assert event["payload"]["id"] == event["event_id"]


@pytest.mark.parametrize("url", [
    "http://example.com/hook", "https://169.254.169.254/latest", "https://10.0.0.5/x",
    "https://[::1]/x", "ftp://example.com",
])
def test_ssrf_guard_blocks_unsafe_destinations(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "environment", "production")
    with pytest.raises(UnsafeDestination):
        validate_destination(url, resolve=False)


def test_localhost_allowed_in_development() -> None:
    validate_destination("http://localhost:8100/webhooks/backit", resolve=False)


def test_public_endpoints_leak_no_private_data(client, campaign, buy) -> None:
    cid = campaign["campaign"]["id"]
    alice = buy(cid, "alice")
    code = alice["backing"]["referral_code"]
    bob = buy(cid, "bob", kind="referral", code=code)
    client.post(f"/v1/orders/{bob['id']}/refund", headers=campaign["headers"])

    pc = client.get(f"/v1/public/campaigns/shipfast?ref={code}")
    assert pc.status_code == 200
    body: dict[str, Any] = pc.json()
    assert body["referrer"]["code"] == code
    assert body["founding"]["spots_taken"] == 1
    assert body["referral"]["price_cents"] == 8000
    ledger = client.get("/v1/public/campaigns/shipfast/ledger").json()
    assert {i["type"] for i in ledger["items"]} >= {"founding_purchase", "referral_purchase", "refund",
                                                    "commission_earned", "commission_reversed"}
    for payload in (body, ledger):
        text = json.dumps(payload)
        assert "@" not in text
        for secret in (alice["id"], bob["id"], "alice", "bob", "MOCK", campaign["secret"]):
            assert secret not in text, secret
    assert client.get("/v1/public/campaigns/nope").status_code == 404
    assert client.get("/v1/public/campaigns/shipfast/ledger?cursor=%%%").status_code == 422


def test_paypal_webhook_requires_valid_signature(client) -> None:
    event = {"id": "WH-1", "event_type": "PAYMENT.CAPTURE.COMPLETED", "resource": {}}
    r = client.post("/v1/webhooks/paypal", json=event)
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "invalid_signature"
    ok = client.post("/v1/webhooks/paypal", json=event, headers={"paypal-transmission-sig": "mock"})
    assert ok.status_code == 200 and ok.json() == {"received": True}
    # Duplicate provider event ids are stored once.
    dup = client.post("/v1/webhooks/paypal", json=event, headers={"paypal-transmission-sig": "mock"})
    assert dup.status_code == 200
