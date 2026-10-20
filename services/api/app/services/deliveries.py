"""Claiming and attempting builder webhook deliveries (used by API and worker)."""

from datetime import timedelta

from sqlalchemy import or_, select, update
from sqlalchemy.orm import Session

from app.ids import utcnow
from app.models import WebhookDelivery
from app.webhooks_out import attempt_delivery

LEASE_SECONDS = 60


def claim(db: Session, delivery_id: str) -> WebhookDelivery | None:
    now = utcnow()
    result = db.execute(
        update(WebhookDelivery)
        .where(
            WebhookDelivery.id == delivery_id,
            WebhookDelivery.state.in_(("pending", "failed")),
            or_(WebhookDelivery.lease_until.is_(None), WebhookDelivery.lease_until < now),
        )
        .values(lease_until=now + timedelta(seconds=LEASE_SECONDS))
        .returning(WebhookDelivery.id)
    )
    claimed = result.scalar_one_or_none()
    db.commit()
    if claimed is None:
        return None
    return db.get(WebhookDelivery, delivery_id, populate_existing=True)


def deliver_now(db: Session, delivery_id: str) -> WebhookDelivery | None:
    """Best-effort immediate attempt; the worker retries anything that fails."""
    delivery = claim(db, delivery_id)
    if delivery is None:
        return db.get(WebhookDelivery, delivery_id)
    attempt_delivery(db, delivery)
    db.commit()
    return delivery


def claim_due(db: Session, limit: int = 20) -> list[str]:
    now = utcnow()
    rows = db.scalars(
        select(WebhookDelivery.id)
        .where(
            WebhookDelivery.state.in_(("pending", "failed")),
            WebhookDelivery.next_attempt_at <= now,
            or_(WebhookDelivery.lease_until.is_(None), WebhookDelivery.lease_until < now),
        )
        .order_by(WebhookDelivery.next_attempt_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    ).all()
    if rows:
        db.execute(
            update(WebhookDelivery)
            .where(WebhookDelivery.id.in_(rows))
            .values(lease_until=now + timedelta(seconds=LEASE_SECONDS))
        )
    db.commit()
    return list(rows)
