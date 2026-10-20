"""Checkout: quoting, reservations, capture and the single idempotent finalize function."""

import re
import secrets
from datetime import timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError, forbidden, not_found
from app.ids import new_id, utcnow
from app.models import Backing, Campaign, Commission, Order, Product, Profile
from app.money import quote_founding, quote_referral
from app.presenters import seller_connection
from app.providers.paypal import CaptureResult, PayPalProvider, ProviderError
from app.schemas import OrderCreate
from app.security import public_ref
from app.services.common import audit, conflict
from app.services.ledger import append_ledger, raise_flag
from app.services.risk import evaluate_referral_purchase
from app.webhooks_out import enqueue_event

CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def normalize_code(code: str) -> str:
    return code.strip().upper()


def generate_referral_code(db: Session, name: str) -> str:
    base = re.sub(r"[^A-Z0-9]", "", name.upper())[:6] or "BACKER"
    while True:
        code = f"{base}-{''.join(secrets.choice(CODE_ALPHABET) for _ in range(4))}"
        if not db.scalars(select(Backing.id).where(Backing.referral_code == code)).first():
            return code


def find_referrer(db: Session, campaign_id: str, code: str | None) -> Backing | None:
    if not code:
        return None
    return db.scalars(
        select(Backing).where(
            Backing.referral_code == normalize_code(code),
            Backing.campaign_id == campaign_id,
            Backing.status == "active",
        )
    ).first()


def _active_reservations(db: Session, campaign_id: str, exclude_order: str | None = None) -> int:
    stmt = select(func.count(Order.id)).where(
        Order.campaign_id == campaign_id,
        Order.kind == "founding",
        Order.state == "created",
        Order.reservation_expires_at > utcnow(),
    )
    if exclude_order:
        stmt = stmt.where(Order.id != exclude_order)
    return int(db.scalar(stmt) or 0)


def _founding_backing(db: Session, campaign_id: str, user_id: str) -> Backing | None:
    return db.scalars(
        select(Backing).where(
            Backing.campaign_id == campaign_id,
            Backing.user_id == user_id,
            Backing.kind == "founding",
        )
    ).first()


def create_order(db: Session, user: Profile, campaign_id: str, body: OrderCreate,
                 paypal: PayPalProvider) -> Order:
    settings = get_settings()
    campaign = db.scalars(
        select(Campaign).where(Campaign.id == campaign_id).with_for_update()
    ).first()
    if campaign is None:
        raise not_found("Campaign")
    if campaign.status != "published":
        raise conflict("campaign_not_published", "This campaign is not accepting purchases")
    product = db.get(Product, campaign.product_id)
    assert product is not None
    conn = seller_connection(db, product.id)
    if conn is None or conn.status != "connected" or not conn.merchant_id:
        raise conflict("seller_not_connected", "The builder's PayPal account is not connected")

    now = utcnow()
    referrer: Backing | None = None
    reservation = None
    if body.kind == "referral":
        referrer = find_referrer(db, campaign.id, body.referral_code)
        if referrer is None:
            raise AppError(422, "invalid_referral_code", "That referral code is not valid for this campaign")
        referrer_profile = db.get(Profile, referrer.user_id)
        same_email = bool(
            referrer_profile and user.email
            and referrer_profile.email.strip().lower() == user.email.strip().lower()
        )
        if referrer.user_id == user.id or same_email:
            raise AppError(422, "self_referral", "You cannot use your own referral code")
        quote = quote_referral(campaign.referral_list_price_cents, campaign.referral_discount_bps,
                               campaign.commission_bps, campaign.platform_fee_bps)
    else:
        if _founding_backing(db, campaign.id, user.id):
            raise conflict("already_backed", "You already hold a founding spot for this campaign")
        for previous in db.scalars(
            select(Order).where(
                Order.campaign_id == campaign.id, Order.buyer_id == user.id,
                Order.kind == "founding", Order.state == "created",
            )
        ).all():
            previous.state = "cancelled"
            previous.failure_reason = "superseded"
        db.flush()
        taken = campaign.founding_spots_taken + _active_reservations(db, campaign.id)
        if taken >= campaign.founding_spots_cap:
            raise conflict("sold_out", "All founding spots are taken or reserved",
                           {"spots_cap": campaign.founding_spots_cap})
        quote = quote_founding(campaign.founding_price_cents, campaign.platform_fee_bps)
        reservation = now + timedelta(minutes=settings.reservation_minutes)

    order = Order(
        id=new_id("ord"),
        campaign_id=campaign.id,
        buyer_id=user.id,
        kind=body.kind,
        state="created",
        currency="USD",
        list_price_cents=quote.list_price_cents,
        discount_cents=quote.discount_cents,
        amount_cents=quote.amount_cents,
        platform_fee_cents=quote.platform_fee_cents,
        commission_cents=quote.commission_cents,
        discount_bps=quote.discount_bps,
        commission_bps=quote.commission_bps,
        platform_fee_bps=quote.platform_fee_bps,
        referral_code=referrer.referral_code if referrer else None,
        referrer_backing_id=referrer.id if referrer else None,
        terms_snapshot={
            "campaign_version": campaign.version,
            "headline": campaign.headline,
            "access_terms": product.access_terms,
            "refund_terms": product.refund_terms,
            "hold_days": settings.hold_days,
        },
        provider=paypal.name,
        merchant_id=conn.merchant_id,
        reservation_expires_at=reservation,
    )
    db.add(order)
    audit(db, actor_id=user.id, action="order.created", target_type="order", target_id=order.id,
          details={"kind": order.kind, "amount_cents": order.amount_cents})
    db.commit()

    web = settings.web_base_url.rstrip("/")
    try:
        created = paypal.create_order(
            order_id=order.id,
            merchant_id=conn.merchant_id,
            amount_cents=order.amount_cents,
            platform_fee_cents=order.platform_fee_cents,
            description=f"{product.name} — {order.kind} purchase",
            return_url=f"{web}/checkout/{order.id}/return",
            cancel_url=f"{web}/checkout/{order.id}/cancel",
        )
    except ProviderError as exc:
        order.state = "failed"
        order.failure_reason = f"create_failed: {exc}"[:500]
        db.commit()
        raise AppError(502, "provider_error", "PayPal could not create the order",
                       {"provider_message": str(exc)}) from exc
    order.paypal_order_id = created.paypal_order_id
    order.approve_url = created.approve_url
    db.commit()
    return order


def _lock_order(db: Session, order_id: str) -> Order:
    order = db.scalars(select(Order).where(Order.id == order_id).with_for_update()).first()
    if order is None:
        raise not_found("Order")
    return order


def capture(db: Session, user: Profile, order_id: str, paypal: PayPalProvider) -> Order:
    order = _lock_order(db, order_id)
    if order.buyer_id != user.id:
        raise forbidden()
    if order.state in ("completed", "refunded"):
        db.commit()
        return order
    if order.state in ("cancelled", "failed"):
        raise conflict("order_not_capturable", f"Order is {order.state}")
    if not order.paypal_order_id:
        raise conflict("order_not_capturable", "Order was not created with the provider")
    if order.state == "created" and order.kind == "founding":
        _ensure_reservation(db, order)
    buyer = db.get(Profile, order.buyer_id)
    assert buyer is not None
    try:
        result = paypal.capture_order(
            paypal_order_id=order.paypal_order_id,
            request_id=f"{order.id}-capture",
            buyer_email=buyer.email,
            buyer_id=buyer.id,
            amount_cents=order.amount_cents,
            merchant_id=order.merchant_id,
        )
    except ProviderError as exc:
        if exc.uncertain:
            order.state = "pending_provider"
            order.failure_reason = "capture_outcome_unknown"
            db.commit()
            return order
        db.commit()
        if exc.issue in ("ORDER_NOT_APPROVED", "PAYER_ACTION_REQUIRED"):
            raise conflict("order_not_approved", "The buyer has not approved this PayPal order") from exc
        raise AppError(502, "provider_error", "PayPal could not capture the payment",
                       {"provider_message": str(exc), "issue": exc.issue}) from exc
    return finalize_capture(db, order, result, source="capture_response")


def _ensure_reservation(db: Session, order: Order) -> None:
    now = utcnow()
    if order.reservation_expires_at and order.reservation_expires_at > now:
        return
    campaign = db.scalars(
        select(Campaign).where(Campaign.id == order.campaign_id).with_for_update()
    ).first()
    assert campaign is not None
    taken = campaign.founding_spots_taken + _active_reservations(db, campaign.id, order.id)
    if taken >= campaign.founding_spots_cap:
        order.state = "cancelled"
        order.failure_reason = "reservation_expired_sold_out"
        db.commit()
        raise conflict("sold_out", "Your reservation expired and all founding spots are taken")
    order.reservation_expires_at = now + timedelta(minutes=get_settings().reservation_minutes)
    db.flush()


def finalize_capture(db: Session, order: Order, result: CaptureResult, *, source: str) -> Order:
    """Idempotently apply a capture outcome. Used by the capture response AND webhooks.

    The caller must hold a row lock on `order` (SELECT ... FOR UPDATE). Commits.
    """
    campaign = db.get(Campaign, order.campaign_id)
    assert campaign is not None
    product = db.get(Product, campaign.product_id)
    assert product is not None

    if order.state in ("completed", "refunded"):
        if result.capture_id and order.paypal_capture_id and result.capture_id != order.paypal_capture_id:
            raise_flag(db, product_id=product.id, campaign_id=campaign.id, order_id=order.id,
                       rule="duplicate_capture_id", subject_key=f"capture:{result.capture_id}",
                       severity="high", evidence={"source": source})
        db.commit()
        return order

    if result.status == "PENDING":
        order.state = "pending_provider"
        order.failure_reason = "capture_pending"
        if result.capture_id and not order.paypal_capture_id:
            order.paypal_capture_id = result.capture_id
        db.commit()
        return order
    if result.status != "COMPLETED":
        order.state = "failed"
        order.failure_reason = f"capture_{result.status.lower()}"
        db.commit()
        return order

    mismatch = (
        result.amount_cents != order.amount_cents
        or (result.currency or "USD") != order.currency
        or (result.merchant_id is not None and order.merchant_id is not None
            and result.merchant_id != order.merchant_id)
    )
    if mismatch:
        order.state = "pending_provider"
        order.failure_reason = "capture_amount_mismatch"
        order.paypal_capture_id = result.capture_id
        raise_flag(db, product_id=product.id, campaign_id=campaign.id, order_id=order.id,
                   rule="capture_amount_mismatch", subject_key=f"order:{order.id}", severity="high",
                   evidence={"expected_cents": order.amount_cents,
                             "captured_cents": result.amount_cents,
                             "currency": result.currency, "source": source})
        db.commit()
        return order

    campaign = db.scalars(
        select(Campaign).where(Campaign.id == order.campaign_id).with_for_update()
    ).one()
    buyer = db.get(Profile, order.buyer_id)
    assert buyer is not None
    now = utcnow()
    order.paypal_capture_id = result.capture_id
    order.payer_id = result.payer_id
    order.payer_email = result.payer_email

    if order.kind == "founding":
        problem = None
        if _founding_backing(db, campaign.id, buyer.id):
            problem = "duplicate_founding_capture"
        elif campaign.founding_spots_taken >= campaign.founding_spots_cap:
            problem = "late_capture_oversold"
        if problem:
            order.state = "pending_provider"
            order.failure_reason = problem
            raise_flag(db, product_id=product.id, campaign_id=campaign.id, order_id=order.id,
                       rule=problem, subject_key=f"order:{order.id}", severity="high",
                       evidence={"source": source, "capture_ref": public_ref("capture", result.capture_id or "")})
            db.commit()
            return order
        campaign.founding_spots_taken += 1
        backing = Backing(
            id=new_id("bck"),
            campaign_id=campaign.id,
            user_id=buyer.id,
            kind="founding",
            badge_number=campaign.founding_spots_taken,
            referral_code=generate_referral_code(db, buyer.display_name),
            status="active",
            order_id=order.id,
        )
        db.add(backing)
        db.flush()
    else:
        backing = db.scalars(
            select(Backing)
            .where(Backing.campaign_id == campaign.id, Backing.user_id == buyer.id)
            .order_by(Backing.kind)  # 'founding' sorts before 'referral'
        ).first()
        if backing is None:
            backing = Backing(
                id=new_id("bck"),
                campaign_id=campaign.id,
                user_id=buyer.id,
                kind="referral",
                badge_number=None,
                referral_code=generate_referral_code(db, buyer.display_name),
                status="active",
                order_id=order.id,
            )
            db.add(backing)
            db.flush()

    order.state = "completed"
    order.completed_at = now
    order.reservation_expires_at = None
    order.failure_reason = None
    order.backing_id = backing.id
    db.flush()

    order_ref = public_ref("order", order.id)
    append_ledger(
        db, campaign_id=campaign.id,
        entry_type="founding_purchase" if order.kind == "founding" else "referral_purchase",
        amount_cents=order.amount_cents, source_key=f"order:{order.id}:purchase",
        public_ref=order_ref, order_id=order.id, backing_id=backing.id, occurred_at=now,
    )

    if order.kind == "referral" and order.referrer_backing_id:
        referrer = db.get(Backing, order.referrer_backing_id)
        assert referrer is not None
        commission = None
        if order.commission_cents > 0:
            commission = Commission(
                id=new_id("com"),
                order_id=order.id,
                backing_id=referrer.id,
                campaign_id=campaign.id,
                product_id=product.id,
                amount_cents=order.commission_cents,
                currency="USD",
                state="held",
                release_at=now + timedelta(days=get_settings().hold_days),
            )
            db.add(commission)
            db.flush()
            append_ledger(
                db, campaign_id=campaign.id, entry_type="commission_earned",
                amount_cents=commission.amount_cents,
                source_key=f"commission:{commission.id}:earned",
                public_ref=public_ref("backing", referrer.id), order_id=order.id,
                backing_id=referrer.id, commission_id=commission.id, occurred_at=now,
            )
        evaluate_referral_purchase(db, order=order, product=product, buyer=buyer,
                                   referrer_backing=referrer, commission=commission)

    if product.webhook_url:
        enqueue_event(db, product, "purchase.completed", {
            "product_id": product.id,
            "campaign_id": campaign.id,
            "order_id": order.id,
            "buyer_email": buyer.email,
            "plan_id": order.kind,
            "amount_cents": order.amount_cents,
            "currency": order.currency,
            "referral_id": order.referrer_backing_id,
        }, order_id=order.id)

    audit(db, actor_id=None, action="order.completed", target_type="order", target_id=order.id,
          details={"source": source, "provider": order.provider, "backing_id": backing.id,
                   "badge_number": backing.badge_number})
    db.commit()
    return order


def cancel_order(db: Session, user: Profile, order_id: str) -> Order:
    order = _lock_order(db, order_id)
    if order.buyer_id != user.id:
        raise forbidden()
    if order.state == "cancelled":
        db.commit()
        return order
    if order.state != "created":
        raise conflict("order_not_cancellable", f"Order is {order.state}")
    order.state = "cancelled"
    order.failure_reason = "buyer_cancelled"
    order.reservation_expires_at = None
    audit(db, actor_id=user.id, action="order.cancelled", target_type="order", target_id=order.id)
    db.commit()
    return order


def visible_order(db: Session, user: Profile, order_id: str) -> Order:
    order = db.get(Order, order_id)
    if order is None:
        raise not_found("Order")
    if order.buyer_id == user.id:
        return order
    campaign = db.get(Campaign, order.campaign_id)
    product = db.get(Product, campaign.product_id) if campaign else None
    if product is None or product.owner_id != user.id:
        raise forbidden()
    return order


def expire_stale_orders(db: Session, paypal: PayPalProvider) -> int:
    """Cancel founding reservations past expiry and abandoned referral orders (>24h)."""
    now = utcnow()
    orders = db.scalars(
        select(Order)
        .where(
            Order.state == "created",
            or_(
                (Order.kind == "founding") & (Order.reservation_expires_at < now),
                (Order.kind == "referral") & (Order.created_at < now - timedelta(hours=24)),
            ),
        )
        .limit(100)
        .with_for_update(skip_locked=True)
    ).all()
    count = 0
    for order in orders:
        if order.paypal_order_id and paypal.name != "mock":
            try:
                status = paypal.get_order_status(order.paypal_order_id)
            except ProviderError:
                continue
            if status in ("APPROVED", "COMPLETED"):
                # The buyer approved; leave it for capture/webhook reconciliation.
                continue
        order.state = "cancelled"
        order.failure_reason = "reservation_expired"
        order.reservation_expires_at = None
        count += 1
    db.commit()
    return count
