from typing import Any

from sqlalchemy import select

from app.models import Commission
from app.services.risk_review import rule_assessment
from tests.conftest import OFFER
from tests.test_refunds_payouts import _ready_for_payout


def _signals(**overrides: Any) -> dict[str, Any]:
    base = {
        "referred_sales": 3, "refunded_sales": 0, "unique_buyers": 3, "repeat_payer_accounts": 0,
        "sales_last_24h": 1, "fastest_gap_minutes": 600.0, "buyers_with_new_accounts": 0,
        "first_sale_minutes_after_backing": 2000, "open_flags": 0,
    }
    return {**base, **overrides}


def test_rule_floor_levels() -> None:
    assert rule_assessment(_signals()) == ("low", [])
    level, reasons = rule_assessment(_signals(sales_last_24h=6, fastest_gap_minutes=0.5))
    assert level == "medium" and len(reasons) == 2
    assert rule_assessment(_signals(refunded_sales=2))[0] == "high"
    assert rule_assessment(_signals(buyers_with_new_accounts=3))[0] == "medium"


def test_preview_includes_risk_review(client, campaign, buy) -> None:
    pid = _ready_for_payout(client, campaign, buy)
    preview = client.post(f"/v1/products/{pid}/payout-previews", headers=campaign["headers"]).json()
    assert preview["risk_source"] == "template"
    risk = preview["items"][0]["risk"]
    # Alice's single referred sale was bought by a buyer who signed up minutes earlier in the test.
    assert risk["level"] in ("low", "medium")
    assert risk["recommendation"] == "pay"
    assert risk["summary"]


def test_hold_then_clear_and_confirm(client, campaign, buy, db, auth) -> None:
    pid = _ready_for_payout(client, campaign, buy)
    h = campaign["headers"]
    preview = client.post(f"/v1/products/{pid}/payout-previews", headers=h).json()
    backing_id = preview["items"][0]["backing_id"]

    r = client.post(f"/v1/payout-previews/{preview['id']}/hold", headers=h, json={"backing_id": backing_id})
    assert r.status_code == 201, r.text
    fresh = r.json()
    assert fresh["items"] == []
    assert [e["reason"] for e in fresh["exclusions"]] == ["risk_review"]
    assert client.get(f"/v1/payout-previews/{preview['id']}", headers=h).json()["status"] == "stale"

    flag = next(f for f in client.get(f"/v1/products/{pid}/risk-flags", headers=h).json()
                if f["rule"] == "builder_hold")
    assert flag["evidence"]["ai_summary"]

    # Only the owner can decide.
    other = client.post(f"/v1/risk-flags/{flag['id']}/decision", json={"decision": "clear"},
                        headers=auth("intruder"))
    assert other.status_code in (403, 404)

    r = client.post(f"/v1/risk-flags/{flag['id']}/decision", headers=h, json={"decision": "clear"})
    assert r.status_code == 200 and r.json()["status"] == "cleared" and r.json()["decided_at"]
    again = client.post(f"/v1/products/{pid}/payout-previews", headers=h).json()
    assert again["total_cents"] == 2000
    assert client.post(f"/v1/risk-flags/{flag['id']}/decision", headers=h,
                       json={"decision": "clear"}).status_code == 409

    # Hold again and confirm: the commission is blocked and stays out of payouts.
    r = client.post(f"/v1/payout-previews/{again['id']}/hold", headers=h, json={"backing_id": backing_id})
    flag2 = next(f for f in client.get(f"/v1/products/{pid}/risk-flags", headers=h).json()
                 if f["rule"] == "builder_hold" and f["status"] == "open")
    r = client.post(f"/v1/risk-flags/{flag2['id']}/decision", headers=h, json={"decision": "confirm"})
    assert r.status_code == 200 and r.json()["status"] == "confirmed"
    db.expire_all()
    assert db.scalars(select(Commission.state)).all() == ["blocked"]
    last = client.post(f"/v1/products/{pid}/payout-previews", headers=h).json()
    assert last["total_cents"] == 0


def test_offer_suggestion_template_is_valid(client, campaign) -> None:
    pid = campaign["product"]["id"]
    h = campaign["headers"]
    r = client.post(f"/v1/products/{pid}/offer-suggestion", headers=h,
                    json={"notes": "Pro plan is $79 a year, for indie hackers.",
                          "list_price_cents": OFFER["referral_list_price_cents"]})
    assert r.status_code == 200, r.text
    s = r.json()
    assert s["source"] == "template"
    assert s["referral_list_price_cents"] == OFFER["referral_list_price_cents"]
    assert s["referral_months"] == 12 and s["founding_price_cents"] == 120900  # just above a friend's $960
    p = s["projection"]
    assert p["friend_pays_cents"] * 1.05 <= s["founding_price_cents"] <= p["friend_pays_cents"] * 1.5
    assert p["friend_pays_cents"] == 96000 and p["backer_earns_cents"] == 24000
    assert p["referral_keep_cents"] == 96000 - 24000 - 7680
    assert p["all_spots_keep_cents"] == p["founding_keep_cents"] * s["founding_spots_cap"]
    assert all(s["reasons"].values())


def test_offer_suggestion_keeps_the_builders_list_price(client, auth) -> None:
    h = auth("solo", "solo@example.com", "Sol Builder")
    product = client.post("/v1/products", headers=h, json={
        "name": "Notely", "url": "https://notely.example.com", "description": "Notes for devs",
        "access_terms": "Lifetime Pro", "refund_terms": "", "webhook_url": None,
    }).json()
    url = f"/v1/products/{product['id']}/offer-suggestion"
    s = client.post(url, headers=h, json={"notes": "Pro is $12/month", "list_price_cents": 7900}).json()
    assert s["referral_list_price_cents"] == 7900 and s["founding_price_cents"] == 94900
    assert "list_price" not in s["reasons"]
    coupon = client.post(url, headers=h, json={"list_price_cents": 7900, "offer_type": "discount", "offer_value": 40})
    assert coupon.status_code == 200 and coupon.json()["referral_list_price_cents"] == 7900
    period = client.post(url, headers=h, json={"list_price_cents": 1200, "referral_months": 6,
                                               "offer_type": "access_period", "offer_value": 12}).json()
    assert period["referral_months"] == 6 and period["founding_price_cents"] < 1200 * 12
    assert period["projection"]["friend_pays_cents"] == 1200 * 6 * 8 // 10
    friend_for_12 = 1200 * 12 * 8 // 10  # what a friend would pay for the same 12 months
    assert friend_for_12 * 0.75 <= period["founding_price_cents"] < friend_for_12
    assert client.post(url, headers=h, json={"notes": "Pro is $79"}).status_code == 422
    r = client.post(url, headers=h, json={"list_price_cents": 100, "offer_type": "access_period", "offer_value": 1})
    assert r.status_code == 422 and r.json()["error"]["code"] == "list_price_too_low"
    assert client.post(url, headers=auth("intruder"), json={"list_price_cents": 7900}).status_code in (403, 404)


PRODUCT = {
    "name": "Shipnote", "url": "https://shipnote.example.com", "description": "Changelogs for indie devs.",
    "access_terms": "Lifetime Pro", "refund_terms": "30-day refund", "webhook_url": None,
}


def test_one_step_new_campaign(client, auth, db) -> None:
    h = auth("onestep", "one@example.com", "Ona Step")
    facts = {k: PRODUCT[k] for k in ("name", "url", "description", "access_terms", "refund_terms")}
    idea = client.post("/v1/products/offer-suggestion", headers=h,
                       json={"product": facts, "notes": "Pro is $59 a year", "list_price_cents": 11900}).json()
    assert idea["referral_list_price_cents"] == 11900 and idea["source"] == "template"
    offer = {k: idea[k] for k in ("founding_price_cents", "founding_spots_cap", "referral_list_price_cents",
                                  "referral_months", "referral_discount_bps", "commission_bps")}
    draft = client.post("/v1/products/campaign-draft", headers=h, json={"product": facts, "offer": offer}).json()
    assert f"${offer['founding_price_cents'] // 100:,}" in draft["story"] and draft["missing_evidence"] == []
    assert draft["founding_price_cents"] == offer["founding_price_cents"]

    campaign = {"slug": "shipnote", "headline": draft["headline"], "summary": draft["summary"],
                "story": draft["story"], **offer}
    r = client.post("/v1/products", headers=h, json={**PRODUCT, "campaign": campaign})
    assert r.status_code == 201, r.text
    product = r.json()
    assert product["webhook_secret"] and product["campaign"]["slug"] == "shipnote"
    assert product["campaign"]["status"] == "draft"

    # A taken address or invalid offer saves nothing.
    before = client.get("/v1/me", headers=h).json()
    r = client.post("/v1/products", headers=h, json={**PRODUCT, "campaign": campaign})
    assert r.status_code == 409 and r.json()["error"]["code"] == "slug_taken"
    bad = {**campaign, "slug": "shipnote-2", "commission_bps": 6000}
    assert client.post("/v1/products", headers=h, json={**PRODUCT, "campaign": bad}).status_code == 422
    assert client.get("/v1/me", headers=h).json() == before


def test_dollar_amounts_ignore_punctuation() -> None:
    from app.money import dollar_amounts_cents
    assert dollar_amounts_cents("Pay $119, then $1,234.5. Or $9.60!") == [11900, 123450, 960]


def test_revenue_threshold_is_100_dollars(client, auth) -> None:
    h = auth("small", "small@example.com", "Small Builder")
    assert client.get("/v1/config").json()["revenue_threshold_cents"] == 10_000
    product = client.post("/v1/products", headers=h, json={**PRODUCT, "name": "Tiny"}).json()
    url = f"/v1/products/{product['id']}/verification/demo"
    v = client.post(url, headers=h, json={"months": [10_000, 25_000, 12_000]}).json()
    assert v["threshold_met"] is True and v["threshold_cents"] == 10_000
    assert client.post(url, headers=h, json={"months": [10_000, 9_999, 12_000]}).json()["threshold_met"] is False
