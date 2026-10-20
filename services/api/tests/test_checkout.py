from typing import Any

from sqlalchemy import func, select

from app.models import Backing, Commission, LedgerEntry, Order
from app.providers.paypal import CaptureResult, get_paypal
from app.services.checkout import finalize_capture


def test_founding_purchase_assigns_badge_and_code(campaign: dict[str, Any], buy) -> None:
    order = buy(campaign["campaign"]["id"], "alice")
    assert order["state"] == "completed"
    assert order["provider"] == "mock"
    assert order["amount_cents"] == 4900
    assert order["commission_cents"] == 0
    assert order["backing"]["badge_number"] == 1
    assert order["backing"]["referral_code"]
    assert order["backing"]["share_url"].endswith(f"?ref={order['backing']['referral_code']}")


def test_founding_one_per_user(client, campaign, buy, auth) -> None:
    cid = campaign["campaign"]["id"]
    buy(cid, "alice")
    r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("alice"), json={"kind": "founding"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "already_backed"


def test_founding_sold_out_counts_reservations(client, campaign, buy, auth) -> None:
    cid = campaign["campaign"]["id"]  # cap = 3
    buy(cid, "a1")
    buy(cid, "a2")
    r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("a3"), json={"kind": "founding"})
    assert r.status_code == 201  # holds the last reservation
    r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("a4"), json={"kind": "founding"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "sold_out"


def test_cancel_releases_reservation(client, campaign, buy, auth) -> None:
    cid = campaign["campaign"]["id"]
    buy(cid, "a1")
    buy(cid, "a2")
    r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("a3"), json={"kind": "founding"})
    assert client.post(f"/v1/orders/{r.json()['id']}/cancel", headers=auth("a3")).json()["state"] == "cancelled"
    assert client.post(f"/v1/campaigns/{cid}/orders", headers=auth("a4"), json={"kind": "founding"}).status_code == 201


def test_referral_attribution_and_pricing(client, campaign, buy) -> None:
    cid = campaign["campaign"]["id"]
    alice = buy(cid, "alice")
    code = alice["backing"]["referral_code"]
    bob = buy(cid, "bob", kind="referral", code=code.lower())
    assert bob["kind"] == "referral"
    assert bob["referral_code"] == code
    assert (bob["list_price_cents"], bob["discount_cents"], bob["amount_cents"],
            bob["platform_fee_cents"], bob["commission_cents"]) == (10000, 2000, 8000, 640, 2000)
    assert bob["backing"]["badge_number"] is None
    assert bob["backing"]["referral_code"] != code

    backings = client.get("/v1/me/backings", headers=campaign["headers"] | {}).json()
    assert backings == []  # builder bought nothing
    from tests.conftest import make_token
    h = {"Authorization": f"Bearer {make_token('alice', 'alice@example.com', 'Alice')}"}
    mine = client.get("/v1/me/backings", headers=h).json()
    assert len(mine) == 1
    assert mine[0]["balances"]["held_cents"] == 2000
    assert mine[0]["commissions"][0]["state"] == "held"


def test_self_referral_and_invalid_code_rejected(client, campaign, buy, auth) -> None:
    cid = campaign["campaign"]["id"]
    alice = buy(cid, "alice")
    code = alice["backing"]["referral_code"]
    r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("alice"),
                    json={"kind": "referral", "referral_code": code})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "self_referral"
    r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("bob"),
                    json={"kind": "referral", "referral_code": "NOPE-0000"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_referral_code"


def test_same_email_different_account_is_self_referral(client, campaign, buy, auth) -> None:
    cid = campaign["campaign"]["id"]
    code = buy(cid, "alice", email="alice@example.com")["backing"]["referral_code"]
    r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("alice2", "Alice@Example.com"),
                    json={"kind": "referral", "referral_code": code})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "self_referral"


def test_capture_and_finalize_are_idempotent(client, campaign, buy, auth, db, sent_webhooks) -> None:
    cid = campaign["campaign"]["id"]
    code = buy(cid, "alice")["backing"]["referral_code"]
    h = auth("bob")
    oid = client.post(f"/v1/campaigns/{cid}/orders", headers=h,
                      json={"kind": "referral", "referral_code": code}).json()["id"]
    first = client.post(f"/v1/orders/{oid}/capture", headers=h).json()
    second = client.post(f"/v1/orders/{oid}/capture", headers=h).json()
    assert first["state"] == second["state"] == "completed"
    assert first["backing"]["id"] == second["backing"]["id"]

    # Replaying the provider webhook path through the same finalize function changes nothing.
    order = db.get(Order, oid)
    result = CaptureResult(
        status="COMPLETED", paypal_order_id=order.paypal_order_id, capture_id=order.paypal_capture_id,
        amount_cents=order.amount_cents,
        currency="USD", payer_email="bob@example.com", payer_id=None, merchant_id=order.merchant_id,
        raw={"provider": "mock"},
    )
    finalize_capture(db, order, result, source="webhook")
    finalize_capture(db, order, result, source="webhook")
    db.expire_all()

    assert db.scalar(select(func.count()).select_from(Commission).where(Commission.order_id == oid)) == 1
    assert db.scalar(select(func.count()).select_from(Backing).where(Backing.campaign_id == cid)) == 2
    ledger = db.scalars(select(LedgerEntry.source_key).where(LedgerEntry.campaign_id == cid)).all()
    assert len(ledger) == len(set(ledger)) == 3  # alice purchase, bob purchase, commission earned
    purchases = [w for w in sent_webhooks if w["payload"]["type"] == "purchase.completed"]
    assert len(purchases) == 2


def test_idempotency_key_replays_order_create(client, campaign, auth) -> None:
    cid = campaign["campaign"]["id"]
    h = auth("alice") | {"Idempotency-Key": "abc-123"}
    r1 = client.post(f"/v1/campaigns/{cid}/orders", headers=h, json={"kind": "founding"})
    r2 = client.post(f"/v1/campaigns/{cid}/orders", headers=h, json={"kind": "founding"})
    assert r1.json()["id"] == r2.json()["id"]
    assert r2.headers.get("Idempotent-Replayed") == "true"


def test_payment_provider_is_mock(campaign) -> None:
    assert type(get_paypal()).__name__ == "MockPayPal"


def test_share_drafts_use_template_with_disclosure(client, campaign, buy, auth) -> None:
    order = buy(campaign["campaign"]["id"], "alice")
    r = client.post(f"/v1/backings/{order['backing']['id']}/share-drafts", headers=auth("alice"),
                    json={"channel": "linkedin"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["source"] == "template"
    text = body["drafts"][0]["text"]
    assert order["backing"]["share_url"] in text
    assert "commission" in text.lower()


def test_builder_sales_masks_buyers(client, campaign, buy) -> None:
    buy(campaign["campaign"]["id"], "alice")
    sales = client.get(f"/v1/products/{campaign['product']['id']}/sales", headers=campaign["headers"]).json()
    assert sales["totals"]["orders"] == 1 and sales["totals"]["captured_cents"] == 4900
    assert sales["orders"][0]["buyer_label"] != "alice@example.com"
