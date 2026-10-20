"""Deterministic risk rules. AI never decides; it may only explain these results."""

from sqlalchemy.orm import Session

from app.models import Backing, Commission, Order, Product, Profile
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
