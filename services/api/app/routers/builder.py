from fastapi import APIRouter
from sqlalchemy import func, select

from app.deps import CurrentUserDep, DBDep
from app.errors import forbidden, not_found
from app.ids import iso, utcnow
from app.models import Commission, Order, Product, Profile, RiskFlag, WebhookDelivery
from app.presenters import delivery_out, risk_out
from app.schemas import RiskFlagOut, SalesOrder, SalesSummary, SalesTotals, WebhookDeliveryOut
from app.security import mask_email
from app.services.common import audit, campaign_for_product, owned_product
from app.services.deliveries import deliver_now

router = APIRouter(tags=["builder"])


@router.get("/products/{product_id}/sales")
def get_sales(product_id: str, user: CurrentUserDep, db: DBDep) -> SalesSummary:
    product = owned_product(db, product_id, user)
    campaign = campaign_for_product(db, product.id)
    empty = SalesTotals(orders=0, captured_cents=0, refunded_cents=0, platform_fee_cents=0,
                        commission_liability_cents=0, commission_paid_cents=0)
    if campaign is None:
        return SalesSummary(totals=empty, orders=[])
    orders = db.scalars(
        select(Order)
        .where(Order.campaign_id == campaign.id,
               Order.state.in_(("completed", "refunded", "pending_provider")))
        .order_by(Order.created_at.desc())
    ).all()
    captured = [o for o in orders if o.state in ("completed", "refunded")]
    refunded = [o for o in orders if o.state == "refunded"]

    def commission_sum(states: tuple[str, ...]) -> int:
        return int(db.scalar(
            select(func.coalesce(func.sum(Commission.amount_cents), 0)).where(
                Commission.campaign_id == campaign.id, Commission.state.in_(states))
        ) or 0)

    totals = SalesTotals(
        orders=len(captured),
        captured_cents=sum(o.amount_cents for o in captured),
        refunded_cents=sum(o.amount_cents for o in refunded),
        platform_fee_cents=sum(o.platform_fee_cents for o in captured if o.state == "completed"),
        commission_liability_cents=commission_sum(
            ("held", "payable", "reserved", "submitted", "blocked")),
        commission_paid_cents=commission_sum(("paid",)),
    )
    out = []
    for o in orders:
        buyer = db.get(Profile, o.buyer_id)
        label = f"{buyer.display_name} ({mask_email(buyer.email)})" if buyer else "hidden"
        out.append(SalesOrder(
            id=o.id, kind=o.kind, state=o.state, buyer_label=label,  # type: ignore[arg-type]
            referral_code=o.referral_code, amount_cents=o.amount_cents,
            platform_fee_cents=o.platform_fee_cents, commission_cents=o.commission_cents,
            created_at=iso(o.created_at) or "",
        ))
    return SalesSummary(totals=totals, orders=out)


@router.get("/products/{product_id}/webhook-deliveries")
def list_webhook_deliveries(product_id: str, user: CurrentUserDep, db: DBDep) -> list[WebhookDeliveryOut]:
    product = owned_product(db, product_id, user)
    rows = db.scalars(
        select(WebhookDelivery).where(WebhookDelivery.product_id == product.id)
        .order_by(WebhookDelivery.created_at.desc()).limit(100)
    ).all()
    return [delivery_out(d) for d in rows]


@router.post("/webhook-deliveries/{delivery_id}/retry")
def retry_webhook_delivery(delivery_id: str, user: CurrentUserDep, db: DBDep) -> WebhookDeliveryOut:
    delivery = db.scalars(
        select(WebhookDelivery).where(WebhookDelivery.id == delivery_id).with_for_update()
    ).first()
    if delivery is None:
        raise not_found("Webhook delivery")
    product = db.get(Product, delivery.product_id)
    if product is None or product.owner_id != user.id:
        raise forbidden()
    if delivery.state == "delivered":
        db.commit()
        return delivery_out(delivery)
    if delivery.state == "dead":
        delivery.max_attempts = delivery.attempts + 3
    delivery.state = "failed" if delivery.attempts else "pending"
    delivery.next_attempt_at = utcnow()
    delivery.lease_until = None
    audit(db, actor_id=user.id, action="webhook_delivery.retried", target_type="webhook_delivery",
          target_id=delivery.id)
    db.commit()
    return delivery_out(deliver_now(db, delivery.id) or delivery)


@router.get("/products/{product_id}/risk-flags")
def list_risk_flags(product_id: str, user: CurrentUserDep, db: DBDep) -> list[RiskFlagOut]:
    product = owned_product(db, product_id, user)
    rows = db.scalars(
        select(RiskFlag).where(RiskFlag.product_id == product.id)
        .order_by(RiskFlag.created_at.desc())
    ).all()
    return [risk_out(r) for r in rows]
