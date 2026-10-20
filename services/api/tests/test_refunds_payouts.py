from typing import Any

from sqlalchemy import select

from app.models import Commission, LedgerEntry
from app.workers import run as worker
from tests.conftest import make_token


def _h(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub, f'{sub}@example.com', sub.title())}"}


def _referral_sale(campaign: dict[str, Any], buy) -> tuple[dict[str, Any], dict[str, Any]]:
    cid = campaign["campaign"]["id"]
    alice = buy(cid, "alice")
    bob = buy(cid, "bob", kind="referral", code=alice["backing"]["referral_code"])
    return alice, bob


def test_refund_reverses_held_commission_and_keeps_badge(client, campaign, buy, db, sent_webhooks) -> None:
    alice, bob = _referral_sale(campaign, buy)
    r = client.post(f"/v1/orders/{bob['id']}/refund", headers=campaign["headers"])
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "refunded"
    commission = db.scalars(select(Commission).where(Commission.order_id == bob["id"])).one()
    assert commission.state == "reversed"
    types = db.scalars(select(LedgerEntry.entry_type).where(LedgerEntry.order_id == bob["id"])).all()
    assert sorted(types) == ["commission_earned", "commission_reversed", "referral_purchase", "refund"]
    refunds = [w for w in sent_webhooks if w["payload"]["type"] == "refund.issued"]
    assert len(refunds) == 1 and refunds[0]["payload"]["data"]["order_id"] == bob["id"]

    # A repeated refund is idempotent: same order back, no new ledger rows or webhooks.
    again = client.post(f"/v1/orders/{bob['id']}/refund", headers=campaign["headers"])
    assert again.status_code == 200 and again.json()["state"] == "refunded"
    db.expire_all()
    assert len(db.scalars(select(LedgerEntry.id).where(LedgerEntry.order_id == bob["id"])).all()) == 4
    assert len([w for w in sent_webhooks if w["payload"]["type"] == "refund.issued"]) == 1

    # Refunding a founding order keeps the permanent badge number.
    assert client.post(f"/v1/orders/{alice['id']}/refund", headers=campaign["headers"]).status_code == 200
    mine = client.get("/v1/me/backings", headers=_h("alice")).json()
    assert mine[0]["badge_number"] == 1
    assert mine[0]["balances"]["reversed_cents"] == 2000


def test_refund_is_owner_only(client, campaign, buy) -> None:
    _, bob = _referral_sale(campaign, buy)
    r = client.post(f"/v1/orders/{bob['id']}/refund", headers=_h("bob"))
    assert r.status_code in (403, 404)


def _ready_for_payout(client, campaign, buy) -> str:
    _referral_sale(campaign, buy)
    r = client.patch("/v1/me", headers=_h("alice"), json={"payout_email": "alice-pay@example.com"})
    assert r.status_code == 200
    pid = campaign["product"]["id"]
    r = client.post(f"/v1/products/{pid}/dev/release-holds", headers=campaign["headers"])
    assert r.status_code == 200 and r.json()["released"] == 1
    return pid


def test_preview_excludes_held_commissions(client, campaign, buy) -> None:
    _referral_sale(campaign, buy)
    pid = campaign["product"]["id"]
    preview = client.post(f"/v1/products/{pid}/payout-previews", headers=campaign["headers"]).json()
    assert preview["total_cents"] == 0
    assert [e["reason"] for e in preview["exclusions"]] == ["in_hold"]


def test_payout_preview_approve_and_mock_execution(client, campaign, buy, db) -> None:
    pid = _ready_for_payout(client, campaign, buy)
    h = campaign["headers"]
    preview = client.post(f"/v1/products/{pid}/payout-previews", headers=h).json()
    assert preview["status"] == "open"
    assert preview["total_cents"] == 2000
    assert preview["items"][0]["payout_email_masked"] != "alice-pay@example.com"
    assert preview["explanation"]["source"] == "template"
    assert "$20.00" in preview["explanation"]["text"]
    assert len(preview["digest"]) >= 32

    # Same state -> same digest.
    again = client.post(f"/v1/products/{pid}/payout-previews", headers=h).json()
    assert again["digest"] == preview["digest"]
    assert client.get(f"/v1/payout-previews/{preview['id']}", headers=h).json()["status"] == "stale"

    r = client.post(f"/v1/payout-previews/{again['id']}/approve", headers=h,
                    json={"digest": "0" * 64, "funding_confirmed": True})
    assert r.status_code == 409 and r.json()["error"]["code"] == "stale_preview"

    r = client.post(f"/v1/payout-previews/{again['id']}/approve", headers=h,
                    json={"digest": again["digest"], "funding_confirmed": True})
    assert r.status_code == 201, r.text
    batch = r.json()
    assert batch["status"] == "queued"
    assert batch["sender_batch_id"].startswith("backit_")
    assert db.scalars(select(Commission.state)).all() == ["reserved"]

    dup = client.post(f"/v1/payout-previews/{again['id']}/approve", headers=h,
                      json={"digest": again["digest"], "funding_confirmed": True})
    assert dup.status_code == 409 and dup.json()["error"]["code"] == "preview_already_approved"

    stats = worker.run_once()
    assert stats["jobs"] >= 1
    done = client.get(f"/v1/payout-batches/{batch['id']}", headers=h).json()
    assert done["status"] == "success"
    assert done["provider_batch_id"].startswith("MOCK")
    assert [i["status"] for i in done["items"]] == ["success"]
    db.expire_all()
    assert db.scalars(select(Commission.state)).all() == ["paid"]
    assert "payout_paid" in db.scalars(select(LedgerEntry.entry_type)).all()
    mine = client.get("/v1/me/backings", headers=_h("alice")).json()
    assert mine[0]["balances"]["paid_cents"] == 2000
    assert len(client.get(f"/v1/products/{pid}/payout-batches", headers=h).json()) == 1

    # Running the worker again does not pay twice.
    worker.run_once()
    db.expire_all()
    assert db.scalars(select(LedgerEntry.entry_type).where(LedgerEntry.entry_type == "payout_paid")).all() == [
        "payout_paid"
    ]


def test_preview_goes_stale_when_commissions_change(client, campaign, buy) -> None:
    pid = _ready_for_payout(client, campaign, buy)
    h = campaign["headers"]
    preview = client.post(f"/v1/products/{pid}/payout-previews", headers=h).json()
    bob_order = client.get(f"/v1/products/{pid}/sales", headers=h).json()["orders"]
    referral = next(o for o in bob_order if o["kind"] == "referral")
    assert client.post(f"/v1/orders/{referral['id']}/refund", headers=h).status_code == 200
    r = client.post(f"/v1/payout-previews/{preview['id']}/approve", headers=h,
                    json={"digest": preview["digest"], "funding_confirmed": True})
    assert r.status_code == 409
    assert r.json()["error"]["code"] in ("stale_preview", "nothing_to_pay")


def test_refund_after_payout_blocks_and_flags(client, campaign, buy, db) -> None:
    pid = _ready_for_payout(client, campaign, buy)
    h = campaign["headers"]
    preview = client.post(f"/v1/products/{pid}/payout-previews", headers=h).json()
    client.post(f"/v1/payout-previews/{preview['id']}/approve", headers=h,
                json={"digest": preview["digest"], "funding_confirmed": True})
    worker.run_once()
    sales = client.get(f"/v1/products/{pid}/sales", headers=h).json()
    referral = next(o for o in sales["orders"] if o["kind"] == "referral")
    assert client.post(f"/v1/orders/{referral['id']}/refund", headers=h).status_code == 200
    flags = client.get(f"/v1/products/{pid}/risk-flags", headers=h).json()
    assert "refund_after_payout" in [f["rule"] for f in flags]
