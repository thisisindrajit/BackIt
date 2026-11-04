from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import email as email_mod
from app.config import get_settings
from app.models import Notification
from app.services import notifications as svc


@pytest.fixture
def sent_emails(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test")

    def fake_send(**kwargs: Any) -> email_mod.EmailResult:
        sent.append(kwargs)
        return email_mod.EmailResult(True, message_id=f"msg_{len(sent)}")

    monkeypatch.setattr(svc, "send_email", fake_send)
    return sent


def test_sales_notify_builder_and_referrer_by_email(
    client: TestClient, auth: Callable[..., dict[str, str]], campaign: dict[str, Any],
    buy: Callable[..., dict[str, Any]], sent_emails: list[dict[str, Any]], db: Any,
) -> None:
    cid = campaign["campaign"]["id"]
    alice = buy(cid, "alice")
    buy(cid, "bob", kind="referral", code=alice["backing"]["referral_code"])

    builder = client.get("/v1/me/notifications", headers=campaign["headers"]).json()
    kinds = [n["kind"] for n in builder["items"]]
    assert kinds == ["sale", "sale", "campaign_live"]
    assert builder["unread_count"] == 3
    assert builder["items"][1]["title"] == "Founding backer #1 for Shipfast"
    assert builder["items"][0]["title"] == "New referral sale for Shipfast"
    assert builder["items"][0]["link"].endswith("?tab=sales")

    referrer = client.get("/v1/me/notifications", headers=auth("alice")).json()
    assert [n["kind"] for n in referrer["items"]] == ["referral_sale"]
    assert "with your referral link" in referrer["items"][0]["body"]

    assert sorted(e["to"] for e in sent_emails) == [
        "alice@example.com", "builder@example.com", "builder@example.com"]
    states = db.scalars(select(Notification.email_state).where(Notification.kind != "campaign_live")).all()
    assert set(states) == {"sent"}
    # The buyer is never notified about their own purchase.
    assert client.get("/v1/me/notifications", headers=auth("bob")).json()["items"] == []


def test_mark_read_and_isolation(
    client: TestClient, auth: Callable[..., dict[str, str]], campaign: dict[str, Any],
    buy: Callable[..., dict[str, Any]], sent_emails: list[dict[str, Any]],
) -> None:
    buy(campaign["campaign"]["id"], "alice")
    h = campaign["headers"]
    items = client.get("/v1/me/notifications", headers=h).json()["items"]
    r = client.post("/v1/me/notifications/read", headers=h, json={"ids": [items[0]["id"]]})
    assert r.json()["unread_count"] == 1
    # Another user cannot mark the builder's notifications.
    client.post("/v1/me/notifications/read", headers=auth("mallory"), json={})
    assert client.get("/v1/me/notifications", headers=h).json()["unread_count"] == 1
    assert client.post("/v1/me/notifications/read", headers=h, json={}).json()["unread_count"] == 0


def test_without_resend_key_emails_are_skipped(
    client: TestClient, campaign: dict[str, Any], buy: Callable[..., dict[str, Any]], db: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "resend_api_key", None)
    order = buy(campaign["campaign"]["id"], "alice")
    n = db.scalars(select(Notification).where(Notification.order_id == order["id"])).one()
    assert n.email_state == "skipped"


def test_failed_email_retries_then_dies(
    client: TestClient, campaign: dict[str, Any], buy: Callable[..., dict[str, Any]], db: Any,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(get_settings(), "resend_api_key", "re_test")
    monkeypatch.setattr(svc, "send_email", lambda **_: email_mod.EmailResult(False, error="503: down"))
    order = buy(campaign["campaign"]["id"], "alice")
    n = db.scalars(select(Notification).where(Notification.order_id == order["id"])).one()
    assert (n.email_state, n.email_attempts) == ("failed", 1)

    monkeypatch.setattr(svc, "send_email",
                        lambda **_: email_mod.EmailResult(False, error="422: bad", retryable=False))
    n.email_next_attempt_at = svc.utcnow()
    db.commit()
    assert svc.send_due_emails(db) == 1
    db.refresh(n)
    assert n.email_state == "dead"


def test_notify_is_idempotent(campaign: dict[str, Any], db: Any) -> None:
    from app.models import Campaign, Product, Profile
    cmp = db.get(Campaign, campaign["campaign"]["id"])
    product = db.get(Product, cmp.product_id)
    owner = db.get(Profile, product.owner_id)
    svc.notify_campaign_live(db, campaign=cmp, product=product, owner=owner)
    svc.notify_campaign_live(db, campaign=cmp, product=product, owner=owner)
    db.commit()
    assert len(db.scalars(select(Notification).where(Notification.kind == "campaign_live")).all()) == 1
