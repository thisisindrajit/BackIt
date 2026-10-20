from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.errors import AppError, forbidden, not_found
from app.ids import new_id, utcnow
from app.models import (
    Backing,
    Campaign,
    Commission,
    Order,
    PayoutAllocation,
    Product,
    Profile,
    Refund,
)
from app.providers.paypal import PayPalProvider, ProviderError
from app.security import public_ref
from app.services.common import audit, conflict
from app.services.ledger import append_ledger, raise_flag
from app.webhooks_out import enqueue_event


def release_matured_holds(db: Session, campaign_id: str | None = None) -> int:
    stmt = (
        update(Commission)
        .where(Commission.state == "held", Commission.release_at <= utcnow())
        .values(state="payable")
    )
    if campaign_id:
        stmt = stmt.where(Commission.campaign_id == campaign_id)
    result = db.execute(stmt)
    return int(result.rowcount or 0)


def refund_order(db: Session, user: Profile, order_id: str,
                 paypal: PayPalProvider) -> tuple[int, Order]:
    order = db.scalars(select(Order).where(Order.id == order_id).with_for_update()).first()
    if order is None:
        raise not_found("Order")
    campaign = db.get(Campaign, order.campaign_id)
    product = db.get(Product, campaign.product_id) if campaign else None
    if product is None or product.owner_id != user.id:
        raise forbidden("Only the campaign owner can refund orders")
    if order.state == "refunded":
        db.commit()
        return 200, order
    if order.state != "completed" or not order.paypal_capture_id:
        raise conflict("order_not_refundable", f"Order is {order.state}")

    refund = db.scalars(select(Refund).where(Refund.order_id == order.id)).first()
    if refund is None:
        refund = Refund(
            id=new_id("rfd"),
            order_id=order.id,
            capture_id=order.paypal_capture_id,
            amount_cents=order.amount_cents,
            state="requested",
            requested_by=user.id,
        )
        db.add(refund)
    elif refund.state == "failed":
        refund.state = "requested"
    audit(db, actor_id=user.id, action="order.refund_requested", target_type="order",
          target_id=order.id, details={"amount_cents": order.amount_cents})
    db.commit()  # Persist intent before contacting the provider.

    try:
        result = paypal.refund_capture(capture_id=order.paypal_capture_id,
                                       amount_cents=order.amount_cents,
                                       request_id=f"{refund.id}-refund")
    except ProviderError as exc:
        if exc.uncertain:
            refund.state = "pending"
            db.commit()
            return 202, order
        refund.state = "failed"
        refund.error = str(exc)[:500]
        db.commit()
        raise AppError(502, "provider_error", "PayPal could not refund the capture",
                       {"provider_message": str(exc)}) from exc
    refund.paypal_refund_id = result.refund_id
    if result.status == "COMPLETED":
        apply_refund(db, order, refund_provider_id=result.refund_id, source="refund_response")
        return 200, order
    if result.status == "PENDING":
        refund.state = "pending"
        db.commit()
        return 202, order
    refund.state = "failed"
    refund.error = f"provider status {result.status}"
    db.commit()
    raise AppError(502, "provider_error", f"PayPal refund {result.status.lower()}")


def apply_refund(db: Session, order: Order, *, refund_provider_id: str | None, source: str) -> Order:
    """Idempotently confirm a full refund. Caller holds the order row lock. Commits."""
    if order.state == "refunded":
        db.commit()
        return order
    now = utcnow()
    campaign = db.get(Campaign, order.campaign_id)
    assert campaign is not None
    product = db.get(Product, campaign.product_id)
    assert product is not None
    refund = db.scalars(select(Refund).where(Refund.order_id == order.id)).first()
    if refund is None:
        refund = Refund(id=new_id("rfd"), order_id=order.id, capture_id=order.paypal_capture_id,
                        amount_cents=order.amount_cents, state="requested")
        db.add(refund)
    refund.state = "completed"
    refund.confirmed_at = now
    if refund_provider_id and not refund.paypal_refund_id:
        refund.paypal_refund_id = refund_provider_id

    order.state = "refunded"
    order.refunded_at = now
    append_ledger(db, campaign_id=campaign.id, entry_type="refund",
                  amount_cents=order.amount_cents, source_key=f"order:{order.id}:refund",
                  public_ref=public_ref("order", order.id), order_id=order.id,
                  backing_id=order.backing_id, occurred_at=now)

    commission = db.scalars(
        select(Commission).where(Commission.order_id == order.id).with_for_update()
    ).first()
    if commission is not None:
        reversal_needed = True
        if commission.state in ("held", "payable", "blocked", "reserved"):
            if commission.state == "reserved":
                db.execute(
                    update(PayoutAllocation)
                    .where(PayoutAllocation.commission_id == commission.id,
                           PayoutAllocation.active.is_(True))
                    .values(active=False)
                )
            commission.state = "reversed"
            commission.reversed_at = now
        elif commission.state in ("submitted", "paid"):
            commission.blocked_reason = "refunded_after_payout"
            raise_flag(db, product_id=product.id, campaign_id=campaign.id, order_id=order.id,
                       backing_id=commission.backing_id, commission_id=commission.id,
                       rule="refund_after_payout", subject_key=f"order:{order.id}",
                       severity="medium",
                       evidence={"commission_state": commission.state,
                                 "amount_cents": commission.amount_cents})
        else:
            reversal_needed = False
        if reversal_needed:
            append_ledger(db, campaign_id=campaign.id, entry_type="commission_reversed",
                          amount_cents=commission.amount_cents,
                          source_key=f"commission:{commission.id}:reversed",
                          public_ref=public_ref("backing", commission.backing_id),
                          order_id=order.id, backing_id=commission.backing_id,
                          commission_id=commission.id, occurred_at=now)

    if order.backing_id:
        backing = db.get(Backing, order.backing_id)
        if backing is not None and backing.order_id == order.id:
            backing.status = "revoked"  # Badge number stays permanently assigned.

    buyer = db.get(Profile, order.buyer_id)
    if product.webhook_url:
        enqueue_event(db, product, "refund.issued", {
            "product_id": product.id,
            "campaign_id": campaign.id,
            "order_id": order.id,
            "buyer_email": buyer.email if buyer else None,
            "plan_id": order.kind,
            "amount_cents": order.amount_cents,
            "currency": order.currency,
            "refund_id": refund.id,
        }, order_id=order.id)
    audit(db, actor_id=None, action="order.refunded", target_type="order", target_id=order.id,
          details={"source": source})
    db.commit()
    return order
