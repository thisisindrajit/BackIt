import json
from typing import Any

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.deps import DBDep, PayPalDep
from app.errors import AppError
from app.ids import new_id
from app.models import ProviderEvent
from app.providers.paypal import PayPalProvider, ProviderError
from app.schemas import AckOut

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

MAX_BODY_BYTES = 256 * 1024


@router.post("/paypal")
async def receive_paypal_webhook(request: Request, db: DBDep, paypal: PayPalDep) -> AckOut:
    raw = await request.body()
    if len(raw) > MAX_BODY_BYTES:
        raise AppError(413, "payload_too_large", "Webhook body too large")
    try:
        event: dict[str, Any] = json.loads(raw)
    except ValueError as exc:
        raise AppError(400, "invalid_payload", "Body must be JSON") from exc
    if not isinstance(event, dict) or not event.get("id") or not event.get("event_type"):
        raise AppError(400, "invalid_payload", "Missing event id or type")
    headers = {k.lower(): v for k, v in request.headers.items()}
    # Signature verification (network) and DB writes are blocking: keep them off the event loop.
    await run_in_threadpool(_verify_and_store, db, paypal, headers, event)
    return AckOut(received=True)


def _verify_and_store(db: Session, paypal: PayPalProvider, headers: dict[str, str],
                      event: dict[str, Any]) -> None:
    try:
        verified = paypal.verify_webhook(headers, event)
    except ProviderError as exc:
        raise AppError(502, "provider_error", "Could not verify webhook signature") from exc
    if not verified:
        raise AppError(400, "invalid_signature", "Webhook signature verification failed")
    resource = event.get("resource") or {}
    db.execute(
        insert(ProviderEvent)
        .values(
            id=new_id("pev"),
            provider=paypal.name,
            provider_event_id=str(event["id"])[:128],
            event_type=str(event["event_type"])[:80],
            resource_id=str(resource.get("id"))[:128] if resource.get("id") else None,
            payload=event,
            verified=True,
            state="received",
            attempts=0,
        )
        .on_conflict_do_nothing(index_elements=["provider", "provider_event_id"])
    )
    db.commit()
