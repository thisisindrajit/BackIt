from typing import Any

from sqlalchemy import select

from app.models import Backing, Notification, Order
from tests.conftest import OFFER
from tests.test_refunds_payouts import _h, _ready_for_payout


def _new_product(client, h: dict[str, str], slug: str) -> str:
    r = client.post("/v1/products", headers=h, json={
        "name": slug.title(), "url": f"https://{slug}.example.com", "description": "A tool",
        "access_terms": "Pro plan", "refund_terms": "30-day refunds",
    })
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_offer_types_validate_and_label(client, auth) -> None:
    h = auth("builder2", "b2@example.com")
    base = {"headline": "Back it", "summary": "Early", "story": "Story", **OFFER}
    pid = _new_product(client, h, "coupons")
    r = client.post("/v1/campaigns", headers=h, json={
        "product_id": pid, "slug": "coupons", **base, "offer_type": "discount"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_offer"
    r = client.post("/v1/campaigns", headers=h, json={
        "product_id": pid, "slug": "coupons", **base, "offer_type": "discount", "offer_value": 40})
    assert r.status_code == 201, r.text
    cmp = r.json()
    assert cmp["offer"] == {"type": "discount", "value": 40, "label": "40% off for life"}

    r = client.patch(f"/v1/campaigns/{cmp['id']}", headers=h, json={"offer_type": "voucher", "offer_value": 5000})
    assert r.json()["offer"]["label"] == "$50 voucher"
    # Switching to a type without a value clears the old value.
    r = client.patch(f"/v1/campaigns/{cmp['id']}", headers=h, json={"offer_type": "lifetime"})
    assert r.json()["offer"] == {"type": "lifetime", "value": None, "label": "Lifetime deal"}
    r = client.patch(f"/v1/campaigns/{cmp['id']}", headers=h, json={"offer_type": "access_period", "offer_value": 12})
    assert r.json()["offer"]["label"] == "1 year of access"


def test_offer_is_locked_after_publish(client, campaign) -> None:
    r = client.patch(f"/v1/campaigns/{campaign['campaign']['id']}", headers=campaign["headers"],
                     json={"offer_type": "discount", "offer_value": 10})
    assert r.status_code == 409 and r.json()["error"]["code"] == "campaign_locked"


def test_same_buyer_cannot_buy_twice(client, campaign, buy, auth) -> None:
    cid = campaign["campaign"]["id"]
    alice = buy(cid, "alice")
    buy(cid, "bob", kind="referral", code=alice["backing"]["referral_code"])
    for body in ({"kind": "founding"}, {"kind": "referral", "referral_code": alice["backing"]["referral_code"]}):
        r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("bob"), json=body)
        assert r.status_code == 409 and r.json()["error"]["code"] == "already_purchased"


def test_demo_backer_can_buy_again(client, campaign, buy, auth, db) -> None:
    cid = campaign["campaign"]["id"]
    first = buy(cid, "demo", email="backer@demo.backit.club")
    second = buy(cid, "demo", email="backer@demo.backit.club")
    assert first["backing"]["badge_number"] == 1 and second["backing"]["badge_number"] == 2
    db.expire_all()
    old = db.scalars(select(Backing).where(Backing.badge_number == 1)).one()
    assert old.user_id != "demo"
    assert db.get(Order, first["id"]).buyer_id == old.user_id
    r = client.get("/v1/me/backings", headers=auth("demo", "backer@demo.backit.club"))
    assert [b["badge_number"] for b in r.json()] == [2]


def test_second_unpaid_checkout_replaces_the_first(client, campaign, buy, auth, db) -> None:
    cid = campaign["campaign"]["id"]
    alice = buy(cid, "alice")
    first = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("carol"), json={"kind": "founding"}).json()
    client.post(f"/v1/campaigns/{cid}/orders", headers=auth("carol"),
                json={"kind": "referral", "referral_code": alice["backing"]["referral_code"]})
    db.expire_all()
    assert db.get(Order, first["id"]).state == "cancelled"
    assert client.post(f"/v1/orders/{first['id']}/capture", headers=auth("carol")).status_code == 409


def test_end_campaign(client, campaign, buy, auth) -> None:
    cid = campaign["campaign"]["id"]
    buy(cid, "alice")
    pending = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("dave"), json={"kind": "founding"}).json()
    assert client.post(f"/v1/campaigns/{cid}/end", headers=_h("alice")).status_code == 403
    r = client.post(f"/v1/campaigns/{cid}/end", headers=campaign["headers"])
    assert r.status_code == 200 and r.json()["status"] == "closed" and r.json()["ended_at"]
    assert client.post(f"/v1/orders/{pending['id']}/capture", headers=auth("dave")).status_code == 409
    r = client.post(f"/v1/campaigns/{cid}/orders", headers=auth("erin"), json={"kind": "founding"})
    assert r.status_code == 409
    page = client.get("/v1/public/campaigns/shipfast").json()
    assert page["status"] == "closed" and page["ended_at"]
    assert all(c["slug"] != "shipfast" for c in client.get("/v1/public/campaigns").json())
    assert client.post(f"/v1/campaigns/{cid}/publish", headers=campaign["headers"]).status_code == 409


def _payable(client, campaign) -> int:
    pid = campaign["product"]["id"]
    preview = client.post(f"/v1/products/{pid}/payout-previews", headers=campaign["headers"]).json()
    return preview["total_cents"], [e["reason"] for e in preview["exclusions"]]


def test_access_report_halts_payouts_until_resolved(client, campaign, buy, db) -> None:
    _ready_for_payout(client, campaign, buy)
    assert _payable(client, campaign)[0] == 2000
    bob_backing = client.get("/v1/me/backings", headers=_h("bob")).json()[0]
    assert bob_backing["access_report"] is None

    assert client.post(f"/v1/backings/{bob_backing['id']}/access-report", headers=_h("alice"),
                       json={"message": "Code does not work at all"}).status_code == 403
    r = client.post(f"/v1/backings/{bob_backing['id']}/access-report", headers=_h("bob"),
                    json={"message": "The code says invalid on checkout"})
    assert r.status_code == 201, r.text
    report: dict[str, Any] = r.json()
    assert client.post(f"/v1/backings/{bob_backing['id']}/access-report", headers=_h("bob"),
                       json={"message": "Still broken, please help"}).status_code == 409

    total, reasons = _payable(client, campaign)
    assert total == 0 and reasons == ["access_report"]
    assert client.get("/v1/public/campaigns/shipfast").json()["trust"]["open_access_reports"] == 1
    assert db.scalars(select(Notification).where(Notification.kind == "access_report")).first() is not None

    pid = campaign["product"]["id"]
    listed = client.get(f"/v1/products/{pid}/access-reports", headers=campaign["headers"]).json()
    assert listed[0]["id"] == report["id"] and listed[0]["backer_name"] == "Bob"
    r = client.post(f"/v1/access-reports/{report['id']}/reply", headers=campaign["headers"],
                    json={"note": "Fixed, try again"})
    assert r.status_code == 200 and r.json()["builder_note"] == "Fixed, try again"
    assert client.post(f"/v1/access-reports/{report['id']}/reply", headers=_h("bob"),
                       json={"note": "nope"}).status_code == 403

    r = client.post(f"/v1/backings/{bob_backing['id']}/access-report/resolve", headers=_h("bob"))
    assert r.status_code == 200 and r.json()["status"] == "resolved"
    assert _payable(client, campaign)[0] == 2000
    assert client.get("/v1/me/backings", headers=_h("bob")).json()[0]["access_report"]["status"] == "resolved"


def test_refund_closes_access_report(client, campaign, buy, db) -> None:
    _ready_for_payout(client, campaign, buy)
    bob_backing = client.get("/v1/me/backings", headers=_h("bob")).json()[0]
    client.post(f"/v1/backings/{bob_backing['id']}/access-report", headers=_h("bob"),
                json={"message": "The code says invalid on checkout"})
    order_id = db.get(Backing, bob_backing["id"]).order_id
    assert client.post(f"/v1/orders/{order_id}/refund", headers=campaign["headers"]).status_code == 200
    assert client.get("/v1/me/backings", headers=_h("bob")).json()[0]["access_report"]["status"] == "refunded"
