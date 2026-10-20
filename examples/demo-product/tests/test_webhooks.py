import json
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from demo_product.main import app, expected_signature

SECRET = "whsec_demo_test"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    db_file = Path(__file__).resolve().parent / f"test-{uuid.uuid4().hex}.sqlite3"
    monkeypatch.setenv("DEMO_DB_PATH", str(db_file))
    monkeypatch.setenv("BACKIT_WEBHOOK_SECRET", SECRET)
    try:
        with TestClient(app) as c:
            yield c
    finally:
        db_file.unlink(missing_ok=True)


def send(client: TestClient, event: dict, *, secret: str = SECRET, ts: int | None = None):
    body = json.dumps(event, separators=(",", ":")).encode()
    timestamp = str(ts if ts is not None else int(time.time()))
    return client.post("/webhooks/backit", content=body, headers={
        "Content-Type": "application/json",
        "BackIt-Event-Id": event["id"],
        "BackIt-Timestamp": timestamp,
        "BackIt-Signature": expected_signature(secret, timestamp, body),
        "BackIt-Key-Version": "1",
    })


def purchase(event_id: str, order_id: str) -> dict:
    return {"id": event_id, "type": "purchase.completed", "version": 1,
            "data": {"order_id": order_id, "buyer_email": f"{order_id}@example.com", "plan_id": "founding"}}


def test_rejects_bad_signature_and_stale_timestamp(client: TestClient) -> None:
    assert send(client, purchase("evt_1", "ord_1"), secret="wrong").status_code == 401
    assert send(client, purchase("evt_1", "ord_1"), ts=int(time.time()) - 301).status_code == 401
    r = client.post("/webhooks/backit", json=purchase("evt_1", "ord_1"))
    assert r.status_code == 401
    assert client.get("/entitlements").json() == []


def test_ping(client: TestClient) -> None:
    r = send(client, {"id": "evt_ping", "type": "ping", "data": {}})
    assert r.status_code == 200 and r.json()["outcome"] == "pong"


def test_grant_dedupe_and_revoke_only_that_order(client: TestClient) -> None:
    assert send(client, purchase("evt_1", "ord_1")).json()["outcome"] == "granted"
    dup = send(client, purchase("evt_1", "ord_1")).json()
    assert dup["duplicate"] is True
    assert send(client, purchase("evt_2", "ord_2")).status_code == 200
    assert len(client.get("/entitlements").json()) == 2

    refund = {"id": "evt_3", "type": "refund.issued", "data": {"order_id": "ord_1"}}
    assert send(client, refund).json()["outcome"] == "revoked"
    ents = {e["order_id"]: e for e in client.get("/entitlements").json()}
    assert ents["ord_1"]["status"] == "revoked" and ents["ord_1"]["revoked_at"]
    assert ents["ord_2"]["status"] == "active" and ents["ord_2"]["revoked_at"] is None
    assert set(ents["ord_2"]) == {"order_id", "buyer_email", "plan_id", "status", "granted_at", "revoked_at"}

    events = client.get("/events").json()
    assert sorted(e["event_id"] for e in events) == ["evt_1", "evt_2", "evt_3"]
