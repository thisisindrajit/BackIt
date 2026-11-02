from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import make_token


def _h(sub: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_token(sub, f'{sub}@example.com', sub.title())}"}


def _redeem(client: TestClient, campaign: dict[str, Any], code: str, user_ref: str,
            secret: str | None = None, product_id: str | None = None):
    return client.post(
        "/v1/claims/redeem",
        headers={"Authorization": f"Bearer {secret or campaign['secret']}"},
        json={"product_id": product_id or campaign["product"]["id"], "code": code, "user_ref": user_ref},
    )


def test_claim_code_redeems_once_per_user(client, campaign, buy) -> None:
    order = buy(campaign["campaign"]["id"], "alice")
    code = order["backing"]["claim_code"]
    assert len(code) == 14 and code.count("-") == 2

    # Lowercase, no dashes and O-for-0 style typos still match.
    typed = code.replace("-", "").lower().replace("0", "o").replace("1", "l")
    r = _redeem(client, campaign, typed, "user_42")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "redeemed"
    assert body["order_id"] == order["id"] and body["plan_id"] == "founding"
    assert body["badge_number"] == 1 and body["buyer_email"] == "alice@example.com"

    again = _redeem(client, campaign, code, "user_42")
    assert again.status_code == 200 and again.json()["status"] == "already_redeemed"
    assert again.json()["claimed_at"] == body["claimed_at"]

    other = _redeem(client, campaign, code, "user_99")
    assert other.status_code == 409 and other.json()["error"]["code"] == "claim_code_used"

    mine = client.get("/v1/me/backings", headers=_h("alice")).json()[0]
    assert mine["claim_code"] == code and mine["claimed_at"] == body["claimed_at"]
    assert mine["status"] == "active" and mine["campaign"]["product_url"].startswith("https://shipfast.example.com")

    sales = client.get(f"/v1/products/{campaign['product']['id']}/sales", headers=campaign["headers"]).json()
    assert sales["orders"][0]["access_claimed_at"] == body["claimed_at"]


def test_claim_requires_product_secret(client, campaign, buy) -> None:
    code = buy(campaign["campaign"]["id"], "alice")["backing"]["claim_code"]
    assert _redeem(client, campaign, code, "u", secret="whsec_wrong").status_code == 401
    assert _redeem(client, campaign, code, "u", product_id="prd_missing").status_code == 401
    r = client.post("/v1/claims/redeem", json={"product_id": campaign["product"]["id"], "code": code, "user_ref": "u"})
    assert r.status_code == 401
    assert _redeem(client, campaign, "ZZZZ-ZZZZ-ZZZZ", "u").status_code == 404


def test_claim_code_is_scoped_to_its_product(client, campaign, buy) -> None:
    code = buy(campaign["campaign"]["id"], "alice")["backing"]["claim_code"]
    r = client.post("/v1/products", headers=campaign["headers"], json={
        "name": "Other", "url": "https://other.example.com", "description": "Another product",
        "access_terms": "Pro", "refund_terms": "30 days", "webhook_url": "http://localhost:8100/webhooks/backit",
    })
    assert r.status_code == 201, r.text
    other = r.json()
    r = _redeem(client, campaign, code, "u", secret=other["webhook_secret"], product_id=other["id"])
    assert r.status_code == 404


def test_refund_revokes_claim_and_reports_claimed_by(client, campaign, buy, sent_webhooks) -> None:
    order = buy(campaign["campaign"]["id"], "alice")
    code = order["backing"]["claim_code"]
    assert _redeem(client, campaign, code, "user_42").status_code == 200
    assert client.post(f"/v1/orders/{order['id']}/refund", headers=campaign["headers"]).status_code == 200

    r = _redeem(client, campaign, code, "user_42")
    assert r.status_code == 410 and r.json()["error"]["code"] == "access_revoked"
    refund = next(w for w in sent_webhooks if w["payload"]["type"] == "refund.issued")
    assert refund["payload"]["data"]["claimed_by"] == "user_42"
