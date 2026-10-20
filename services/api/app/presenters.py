"""Convert ORM rows to public API schemas."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ids import iso
from app.models import (
    Backing,
    Campaign,
    Commission,
    LedgerEntry,
    Order,
    PayoutBatch,
    PayoutItem,
    PayoutPreview,
    Product,
    Profile,
    RevenueVerification,
    RiskFlag,
    SellerConnection,
    WebhookDelivery,
)
from app.schemas import (
    BackingCampaign,
    BackingOut,
    Balances,
    CampaignOut,
    CommissionOut,
    Explanation,
    Funding,
    OrderAccess,
    OrderBacking,
    OrderOut,
    PayoutBatchItemOut,
    PayoutBatchOut,
    PayoutPreviewOut,
    PreviewExclusion,
    PreviewItem,
    ProductOut,
    ProfileOut,
    RiskFlagOut,
    SellerConnectionOut,
    VerificationMonth,
    VerificationOut,
    WebhookDeliveryOut,
)
from app.security import public_ref


def profile_out(p: Profile) -> ProfileOut:
    return ProfileOut(
        id=p.id,
        email=p.email,
        display_name=p.display_name,
        payout_email=p.payout_email,
        payout_email_verified=p.payout_email_verified,
    )


def default_provider() -> str:
    return "paypal_sandbox" if get_settings().paypal_mode == "sandbox" else "mock"


def seller_connection(db: Session, product_id: str) -> SellerConnection | None:
    return db.scalars(
        select(SellerConnection).where(SellerConnection.product_id == product_id)
    ).first()


def seller_out(conn: SellerConnection | None) -> SellerConnectionOut:
    if conn is None:
        return SellerConnectionOut(
            status="not_connected",
            merchant_id=None,
            provider=default_provider(),  # type: ignore[arg-type]
            checked_at=None,
            payments_receivable=False,
        )
    return SellerConnectionOut(
        status=conn.status,  # type: ignore[arg-type]
        merchant_id=conn.merchant_id,
        provider=conn.provider,  # type: ignore[arg-type]
        checked_at=iso(conn.checked_at),
        payments_receivable=conn.payments_receivable,
    )


def latest_verification(db: Session, product_id: str) -> RevenueVerification | None:
    return db.scalars(
        select(RevenueVerification)
        .where(RevenueVerification.product_id == product_id)
        .order_by(RevenueVerification.checked_at.desc(), RevenueVerification.id.desc())
    ).first()


def verification_out(v: RevenueVerification | None) -> VerificationOut | None:
    if v is None:
        return None
    return VerificationOut(
        source=v.source,  # type: ignore[arg-type]
        is_demo=v.is_demo,
        months=[VerificationMonth(**m) for m in v.months],
        threshold_cents=v.threshold_cents,
        threshold_met=v.threshold_met,
        checked_at=iso(v.checked_at) or "",
    )


def campaign_out(c: Campaign) -> CampaignOut:
    return CampaignOut(
        id=c.id,
        product_id=c.product_id,
        slug=c.slug,
        status=c.status,  # type: ignore[arg-type]
        version=c.version,
        headline=c.headline,
        summary=c.summary,
        story=c.story,
        founding_price_cents=c.founding_price_cents,
        founding_spots_cap=c.founding_spots_cap,
        founding_spots_taken=c.founding_spots_taken,
        referral_list_price_cents=c.referral_list_price_cents,
        referral_discount_bps=c.referral_discount_bps,
        commission_bps=c.commission_bps,
        platform_fee_bps=c.platform_fee_bps,
        published_at=iso(c.published_at),
        updated_at=iso(c.updated_at) or "",
    )


def product_out(db: Session, product: Product) -> ProductOut:
    campaign = db.scalars(select(Campaign).where(Campaign.product_id == product.id)).first()
    return ProductOut(
        id=product.id,
        name=product.name,
        slug=product.slug,
        url=product.url,
        description=product.description,
        access_terms=product.access_terms,
        refund_terms=product.refund_terms,
        webhook_url=product.webhook_url,
        webhook_secret_hint=product.webhook_secret_hint,
        seller=seller_out(seller_connection(db, product.id)),
        verification=verification_out(latest_verification(db, product.id)),
        campaign=campaign_out(campaign) if campaign else None,
        created_at=iso(product.created_at) or "",
    )


def share_url(campaign_slug: str, code: str) -> str:
    return f"{get_settings().web_base_url.rstrip('/')}/{campaign_slug}?ref={code}"


def order_access(db: Session, order: Order, product: Product) -> OrderAccess:
    delivery = db.scalars(
        select(WebhookDelivery)
        .where(
            WebhookDelivery.order_id == order.id,
            WebhookDelivery.event_type == "purchase.completed",
        )
        .order_by(WebhookDelivery.created_at.desc())
    ).first()
    if delivery is None:
        status = "pending" if product.webhook_url else "not_configured"
        return OrderAccess(status=status, last_attempt_at=None)  # type: ignore[arg-type]
    mapping = {"delivered": "delivered", "dead": "failed", "failed": "pending", "pending": "pending"}
    return OrderAccess(
        status=mapping[delivery.state],  # type: ignore[arg-type]
        last_attempt_at=iso(delivery.last_attempt_at),
    )


def order_out(db: Session, order: Order) -> OrderOut:
    campaign = db.get(Campaign, order.campaign_id)
    assert campaign is not None
    product = db.get(Product, campaign.product_id)
    assert product is not None
    backing = db.get(Backing, order.backing_id) if order.backing_id else None
    return OrderOut(
        id=order.id,
        campaign_id=order.campaign_id,
        campaign_slug=campaign.slug,
        kind=order.kind,  # type: ignore[arg-type]
        state=order.state,  # type: ignore[arg-type]
        list_price_cents=order.list_price_cents,
        discount_cents=order.discount_cents,
        amount_cents=order.amount_cents,
        platform_fee_cents=order.platform_fee_cents,
        commission_cents=order.commission_cents,
        referral_code=order.referral_code,
        provider=order.provider,  # type: ignore[arg-type]
        paypal_order_id=order.paypal_order_id,
        reservation_expires_at=iso(order.reservation_expires_at)
        if order.state == "created"
        else None,
        backing=OrderBacking(
            id=backing.id,
            badge_number=backing.badge_number,
            referral_code=backing.referral_code,
            share_url=share_url(campaign.slug, backing.referral_code),
        )
        if backing
        else None,
        access=order_access(db, order, product),
        created_at=iso(order.created_at) or "",
    )


def balances_for(db: Session, backing_id: str) -> Balances:
    rows = db.execute(
        select(Commission.state, func.coalesce(func.sum(Commission.amount_cents), 0))
        .where(Commission.backing_id == backing_id)
        .group_by(Commission.state)
    ).all()
    by_state = {state: int(total) for state, total in rows}
    reversed_total = db.scalar(
        select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(
            LedgerEntry.backing_id == backing_id,
            LedgerEntry.entry_type == "commission_reversed",
        )
    )
    return Balances(
        held_cents=by_state.get("held", 0),
        payable_cents=by_state.get("payable", 0),
        reserved_cents=by_state.get("reserved", 0) + by_state.get("submitted", 0),
        paid_cents=by_state.get("paid", 0),
        reversed_cents=int(reversed_total or 0),
    )


def backing_out(db: Session, backing: Backing) -> BackingOut:
    campaign = db.get(Campaign, backing.campaign_id)
    assert campaign is not None
    product = db.get(Product, campaign.product_id)
    assert product is not None
    commissions = db.scalars(
        select(Commission)
        .where(Commission.backing_id == backing.id)
        .order_by(Commission.created_at.desc())
    ).all()
    return BackingOut(
        id=backing.id,
        kind=backing.kind,  # type: ignore[arg-type]
        campaign=BackingCampaign(
            id=campaign.id, slug=campaign.slug, headline=campaign.headline,
            product_name=product.name,
        ),
        badge_number=backing.badge_number,
        referral_code=backing.referral_code,
        share_url=share_url(campaign.slug, backing.referral_code),
        balances=balances_for(db, backing.id),
        commissions=[
            CommissionOut(
                id=c.id,
                order_ref=public_ref("order", c.order_id),
                amount_cents=c.amount_cents,
                state=c.state,  # type: ignore[arg-type]
                release_at=iso(c.release_at) or "",
                created_at=iso(c.created_at) or "",
            )
            for c in commissions
        ],
        created_at=iso(backing.created_at) or "",
    )


def delivery_out(d: WebhookDelivery) -> WebhookDeliveryOut:
    return WebhookDeliveryOut(
        id=d.id,
        event_id=d.event_id,
        event_type=d.event_type,
        state=d.state,  # type: ignore[arg-type]
        attempts=d.attempts,
        last_status_code=d.last_status_code,
        last_error=d.last_error,
        next_attempt_at=iso(d.next_attempt_at),
        created_at=iso(d.created_at) or "",
    )


def risk_out(r: RiskFlag) -> RiskFlagOut:
    return RiskFlagOut(
        id=r.id,
        rule=r.rule,
        severity=r.severity,
        status=r.status,
        evidence=r.evidence,
        explanation=r.explanation,
        created_at=iso(r.created_at) or "",
    )


def preview_out(p: PayoutPreview) -> PayoutPreviewOut:
    return PayoutPreviewOut(
        id=p.id,
        product_id=p.product_id,
        status=p.status,  # type: ignore[arg-type]
        digest=p.digest,
        total_cents=p.total_cents,
        currency="USD",
        items=[
            PreviewItem(
                backing_id=i["backing_id"],
                backer_name=i["backer_name"],
                payout_email_masked=i["payout_email_masked"],
                amount_cents=i["amount_cents"],
                commission_ids=i["commission_ids"],
            )
            for i in p.items
        ],
        exclusions=[PreviewExclusion(**e) for e in p.exclusions],
        funding=Funding(**p.funding),
        explanation=Explanation(text=p.explanation_text, source=p.explanation_source),  # type: ignore[arg-type]
        created_at=iso(p.created_at) or "",
        expires_at=iso(p.expires_at) or "",
    )


def batch_out(db: Session, batch: PayoutBatch) -> PayoutBatchOut:
    items = db.scalars(
        select(PayoutItem).where(PayoutItem.batch_id == batch.id).order_by(PayoutItem.id)
    ).all()
    out_items = []
    for item in items:
        backing = db.get(Backing, item.backing_id)
        profile = db.get(Profile, backing.user_id) if backing else None
        out_items.append(
            PayoutBatchItemOut(
                id=item.id,
                backer_name=profile.display_name if profile else "Backer",
                amount_cents=item.amount_cents,
                status=item.status,  # type: ignore[arg-type]
                provider_item_id=item.provider_item_id,
            )
        )
    return PayoutBatchOut(
        id=batch.id,
        product_id=batch.product_id,
        preview_id=batch.preview_id,
        status=batch.status,  # type: ignore[arg-type]
        sender_batch_id=batch.sender_batch_id,
        provider_batch_id=batch.provider_batch_id,
        total_cents=batch.total_cents,
        items=out_items,
        approved_by=batch.approved_by,
        approved_at=iso(batch.approved_at) or "",
        summary=batch.summary,
    )
