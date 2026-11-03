"""Deterministic risk rules. AI never decides; it may only explain these results."""

from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import not_found
from app.ids import utcnow
from app.models import Backing, Commission, Order, PayoutAllocation, Product, Profile, RiskFlag
from app.services.common import audit, conflict, owned_product
from app.services.ledger import raise_flag


def _norm(value: str | None) -> str | None:
    return value.strip().lower() if value else None


def evaluate_referral_purchase(
    db: Session,
    *,
    order: Order,
    product: Product,
    buyer: Profile,
    referrer_backing: Backing,
    commission: Commission | None,
) -> list[str]:
    referrer = db.get(Profile, referrer_backing.user_id)
    referrer_order = db.get(Order, referrer_backing.order_id)
    triggered: list[tuple[str, dict]] = []
    payer_email = _norm(order.payer_email)
    buyer_email = _norm(buyer.email)
    if referrer is not None:
        referrer_email = _norm(referrer.email)
        payout_email = _norm(referrer.payout_email)
        if payer_email and payer_email in {referrer_email, payout_email}:
            triggered.append(("self_referral_email", {"match": "payer_email_equals_referrer_email"}))
        if payout_email and payout_email in {buyer_email, payer_email}:
            triggered.append(
                ("payout_email_matches_buyer", {"match": "referrer_payout_email_equals_buyer"})
            )
    if (
        referrer_order is not None
        and order.payer_id
        and referrer_order.payer_id
        and order.payer_id == referrer_order.payer_id
    ):
        triggered.append(("self_referral_payer", {"match": "same_paypal_payer_account"}))

    for rule, evidence in triggered:
        raise_flag(
            db,
            product_id=product.id,
            campaign_id=order.campaign_id,
            order_id=order.id,
            backing_id=referrer_backing.id,
            commission_id=commission.id if commission else None,
            rule=rule,
            subject_key=f"order:{order.id}",
            severity="high",
            evidence={**evidence, "order_ref": order.id, "referral_code": order.referral_code},
        )
    if triggered and commission is not None:
        commission.state = "blocked"
        commission.blocked_reason = triggered[0][0]
    return [rule for rule, _ in triggered]


def decide_flag(db: Session, user: Profile, flag_id: str, decision: Literal["clear", "confirm"]) -> RiskFlag:
    """Builder clears (pay normally) or confirms (keep commissions blocked) an open flag."""
    flag = db.get(RiskFlag, flag_id)
    if flag is None:
        raise not_found("Risk flag")
    owned_product(db, flag.product_id, user, lock=True)
    flag = db.scalars(select(RiskFlag).where(RiskFlag.id == flag_id).with_for_update()).one()
    if flag.status != "open":
        raise conflict("flag_decided", "This flag has already been reviewed.")
    now = utcnow()
    flag.status = "cleared" if decision == "clear" else "confirmed"
    flag.reviewer_id = user.id
    flag.decided_at = now

    if decision == "clear" and flag.commission_id:
        c = db.get(Commission, flag.commission_id)
        still_flagged = db.scalar(select(func.count(RiskFlag.id)).where(
            RiskFlag.commission_id == flag.commission_id, RiskFlag.status == "open", RiskFlag.id != flag.id))
        if c is not None and c.state == "blocked" and c.blocked_reason == flag.rule and not still_flagged:
            c.state = "payable" if c.release_at <= now else "held"
            c.blocked_reason = None
    elif decision == "confirm" and flag.backing_id and flag.rule == "builder_hold":
        allocated = select(PayoutAllocation.commission_id).where(PayoutAllocation.active.is_(True))
        for c in db.scalars(select(Commission).where(
            Commission.backing_id == flag.backing_id,
            Commission.state.in_(("held", "payable")),
            Commission.id.not_in(allocated),
        )).all():
            c.state = "blocked"
            c.blocked_reason = "builder_hold"
    audit(db, actor_id=user.id, action=f"risk_flag.{flag.status}", target_type="risk_flag",
          target_id=flag.id, details={"rule": flag.rule})
    db.commit()
    return flag
