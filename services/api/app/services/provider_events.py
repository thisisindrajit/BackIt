"""Inbox processing for verified PayPal webhook events."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ids import new_id, utcnow
from app.models import Order, OutboxJob, PayoutBatch, ProviderEvent, SellerConnection
from app.money import decimal_string_to_cents
from app.providers.paypal import CaptureResult, PayPalProvider
from app.services.checkout import finalize_capture
from app.services.refunds import apply_refund


def _cents(amount: dict[str, Any] | None) -> int | None:
    if not amount or "value" not in amount:
        return None
    return decimal_string_to_cents(str(amount["value"]))


def _order_for(db: Session, resource: dict[str, Any]) -> Order | None:
    related = (resource.get("supplementary_data") or {}).get("related_ids") or {}
    paypal_order_id = related.get("order_id")
    capture_id = resource.get("id")
    stmt = select(Order).with_for_update()
    if paypal_order_id:
        order = db.scalars(stmt.where(Order.paypal_order_id == paypal_order_id)).first()
        if order:
            return order
    if capture_id:
        return db.scalars(stmt.where(Order.paypal_capture_id == capture_id)).first()
    return None


def _enqueue_reconcile(db: Session, batch: PayoutBatch) -> None:
    db.add(OutboxJob(id=new_id("job"), kind="execute_payout", payload={"batch_id": batch.id},
                     dedupe_key=None, state="pending", max_attempts=6, next_attempt_at=utcnow()))


def process_event(db: Session, event: ProviderEvent, paypal: PayPalProvider) -> str:
    """Apply one event. Returns the resulting state ('processed' or 'ignored'). Commits."""
    payload = event.payload or {}
    resource: dict[str, Any] = payload.get("resource") or {}
    etype = event.event_type

    if etype == "PAYMENT.CAPTURE.COMPLETED":
        order = _order_for(db, resource)
        if order is None:
            return "ignored"
        payee = resource.get("payee") or {}
        amount = resource.get("amount") or {}
        result = CaptureResult(
            status="COMPLETED",
            paypal_order_id=order.paypal_order_id or "",
            capture_id=resource.get("id"),
            amount_cents=_cents(amount),
            currency=amount.get("currency_code"),
            payer_id=order.payer_id,
            payer_email=order.payer_email,
            merchant_id=payee.get("merchant_id"),
            raw=resource,
        )
        finalize_capture(db, order, result, source="webhook")
        return "processed"

    if etype in ("PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED"):
        # For refunds the resource is the refund; the capture link carries the capture id.
        capture_id = None
        for link in resource.get("links") or []:
            if link.get("rel") == "up" and "/captures/" in (link.get("href") or ""):
                capture_id = link["href"].rstrip("/").split("/")[-1]
        if etype == "PAYMENT.CAPTURE.REVERSED":
            capture_id = resource.get("id")
        if not capture_id:
            return "ignored"
        order = db.scalars(
            select(Order).where(Order.paypal_capture_id == capture_id).with_for_update()
        ).first()
        if order is None or order.state not in ("completed", "refunded"):
            return "ignored"
        refund_id = resource.get("id") if etype == "PAYMENT.CAPTURE.REFUNDED" else None
        apply_refund(db, order, refund_provider_id=refund_id, source="webhook")
        return "processed"

    if etype == "PAYMENT.CAPTURE.DENIED":
        order = _order_for(db, resource)
        if order is None:
            return "ignored"
        if order.state in ("created", "pending_provider"):
            order.state = "failed"
            order.failure_reason = "capture_denied"
        db.commit()
        return "processed"

    if etype.startswith("PAYMENT.PAYOUTSBATCH") or etype.startswith("PAYMENT.PAYOUTS-ITEM"):
        header = resource.get("batch_header") or {}
        batch_id = header.get("payout_batch_id") or resource.get("payout_batch_id")
        if not batch_id:
            return "ignored"
        batch = db.scalars(select(PayoutBatch).where(PayoutBatch.provider_batch_id == batch_id)).first()
        if batch is None:
            return "ignored"
        _enqueue_reconcile(db, batch)
        db.commit()
        return "processed"

    if etype in ("MERCHANT.ONBOARDING.COMPLETED", "MERCHANT.PARTNER-CONSENT.REVOKED"):
        tracking_id = resource.get("tracking_id")
        conn = db.scalars(
            select(SellerConnection).where(SellerConnection.tracking_id == tracking_id)
        ).first() if tracking_id else None
        if conn is None:
            return "ignored"
        if etype == "MERCHANT.PARTNER-CONSENT.REVOKED":
            conn.status = "failed"
            conn.payments_receivable = False
        else:
            conn.merchant_id = resource.get("merchant_id") or conn.merchant_id
            # Capabilities are confirmed by the status endpoint; mark pending until checked.
            if conn.status != "connected":
                conn.status = "pending"
        conn.checked_at = utcnow()
        db.commit()
        return "processed"

    return "ignored"
