from fastapi import APIRouter
from sqlalchemy import select

from app.deps import CurrentUserDep, DBDep, IdempotencyKeyHeader, PayPalDep
from app.models import WebhookDelivery
from app.presenters import order_out
from app.schemas import OrderOut
from app.services import checkout
from app.services.deliveries import deliver_now
from app.services.idempotency import run_idempotent
from app.services.refunds import refund_order

router = APIRouter(prefix="/orders", tags=["orders"])


def _deliver_pending(db: DBDep, order_id: str) -> None:
    ids = db.scalars(select(WebhookDelivery.id).where(
        WebhookDelivery.order_id == order_id, WebhookDelivery.state == "pending",
        WebhookDelivery.attempts == 0)).all()
    for delivery_id in ids:
        deliver_now(db, delivery_id)


@router.get("/{order_id}")
def get_order(order_id: str, user: CurrentUserDep, db: DBDep) -> OrderOut:
    return order_out(db, checkout.visible_order(db, user, order_id))


@router.post(
    "/{order_id}/capture",
    responses={202: {"model": OrderOut, "description": "Provider outcome uncertain (pending_provider)"}},
)
def capture_order(
    order_id: str,
    user: CurrentUserDep,
    db: DBDep,
    paypal: PayPalDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> OrderOut:
    def action() -> tuple[int, OrderOut]:
        order = checkout.capture(db, user, order_id, paypal)
        if order.state == "completed":
            _deliver_pending(db, order.id)
        return (202 if order.state == "pending_provider" else 200), order_out(db, order)

    return run_idempotent(  # type: ignore[return-value]
        db, user_id=user.id, scope=f"capture:{order_id}", key=idempotency_key, body={},
        action=action,
    )


@router.post("/{order_id}/cancel")
def cancel_order(order_id: str, user: CurrentUserDep, db: DBDep) -> OrderOut:
    return order_out(db, checkout.cancel_order(db, user, order_id))


@router.post(
    "/{order_id}/refund",
    responses={202: {"model": OrderOut, "description": "Refund pending at provider"}},
)
def refund(
    order_id: str,
    user: CurrentUserDep,
    db: DBDep,
    paypal: PayPalDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> OrderOut:
    def action() -> tuple[int, OrderOut]:
        status_code, order = refund_order(db, user, order_id, paypal)
        if order.state == "refunded":
            _deliver_pending(db, order.id)
        return status_code, order_out(db, order)

    return run_idempotent(  # type: ignore[return-value]
        db, user_id=user.id, scope=f"refund:{order_id}", key=idempotency_key, body={},
        action=action,
    )
