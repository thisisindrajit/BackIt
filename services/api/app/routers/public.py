import base64
import binascii
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Query
from sqlalchemy import and_, func, or_, select

from app.config import get_settings
from app.deps import DBDep
from app.errors import AppError, not_found
from app.ids import iso
from app.models import Backing, Campaign, LedgerEntry, Order, Product, Profile
from app.money import quote_referral
from app.presenters import latest_verification, seller_connection, verification_out
from app.schemas import (
    LedgerItem,
    LedgerPage,
    PublicCampaign,
    PublicFounding,
    PublicProduct,
    PublicReferral,
    PublicReferrer,
    PublicStats,
    PublicTrust,
)
from app.services.checkout import find_referrer

router = APIRouter(prefix="/public", tags=["public"])
PAGE_SIZE = 20


def _published(db: DBDep, slug: str) -> Campaign:
    campaign = db.scalars(select(Campaign).where(Campaign.slug == slug.lower())).first()
    if campaign is None or campaign.status != "published":
        raise not_found("Campaign")
    return campaign


@router.get("/campaigns/{slug}")
def get_public_campaign(
    slug: str, db: DBDep, ref: Annotated[str | None, Query(max_length=32)] = None
) -> PublicCampaign:
    settings = get_settings()
    campaign = _published(db, slug)
    product = db.get(Product, campaign.product_id)
    assert product is not None
    owner = db.get(Profile, product.owner_id)
    conn = seller_connection(db, product.id)
    quote = quote_referral(campaign.referral_list_price_cents, campaign.referral_discount_bps,
                           campaign.commission_bps, campaign.platform_fee_bps)
    referrer = None
    backing = find_referrer(db, campaign.id, ref)
    if backing is not None:
        ref_profile = db.get(Profile, backing.user_id)
        referrer = PublicReferrer(code=backing.referral_code,
                                  display_name=ref_profile.display_name if ref_profile else "A backer")
    backers = db.scalar(select(func.count(Backing.id)).where(Backing.campaign_id == campaign.id)) or 0
    sales = db.scalar(select(func.count(Order.id)).where(
        Order.campaign_id == campaign.id, Order.state == "completed")) or 0
    return PublicCampaign(
        id=campaign.id,
        slug=campaign.slug,
        headline=campaign.headline,
        summary=campaign.summary,
        story=campaign.story,
        status=campaign.status,  # type: ignore[arg-type]
        product=PublicProduct(name=product.name, url=product.url),
        builder_name=owner.display_name if owner else "Builder",
        founding=PublicFounding(
            price_cents=campaign.founding_price_cents,
            spots_cap=campaign.founding_spots_cap,
            spots_taken=campaign.founding_spots_taken,
            spots_left=max(campaign.founding_spots_cap - campaign.founding_spots_taken, 0),
        ),
        referral=PublicReferral(
            list_price_cents=quote.list_price_cents,
            discount_bps=quote.discount_bps,
            price_cents=quote.amount_cents,
            commission_bps=quote.commission_bps,
            commission_cents=quote.commission_cents,
        ),
        platform_fee_bps=campaign.platform_fee_bps,
        trust=PublicTrust(
            verification=verification_out(latest_verification(db, product.id)),
            seller_connected=bool(conn and conn.status == "connected"),
            seller_provider=(conn.provider if conn else
                             ("paypal_sandbox" if settings.paypal_mode == "sandbox" else "mock")),  # type: ignore[arg-type]
            access_terms=product.access_terms,
            refund_terms=product.refund_terms,
            hold_days=settings.hold_days,
            payout_minimum_cents=settings.payout_minimum_cents,
        ),
        stats=PublicStats(backers=int(backers), sales=int(sales)),
        referrer=referrer,
    )


def _encode_cursor(entry: LedgerEntry) -> str:
    raw = f"{entry.occurred_at.isoformat()}|{entry.id}"
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        occurred, entry_id = base64.urlsafe_b64decode(padded).decode().split("|", 1)
        return datetime.fromisoformat(occurred), entry_id
    except (ValueError, binascii.Error, UnicodeDecodeError) as exc:
        raise AppError(422, "invalid_cursor", "The cursor is not valid") from exc


@router.get("/campaigns/{slug}/ledger")
def get_public_ledger(
    slug: str, db: DBDep, cursor: Annotated[str | None, Query(max_length=200)] = None
) -> LedgerPage:
    campaign = _published(db, slug)
    stmt = select(LedgerEntry).where(LedgerEntry.campaign_id == campaign.id)
    if cursor:
        occurred, entry_id = _decode_cursor(cursor)
        stmt = stmt.where(or_(
            LedgerEntry.occurred_at < occurred,
            and_(LedgerEntry.occurred_at == occurred, LedgerEntry.id < entry_id),
        ))
    rows = db.scalars(
        stmt.order_by(LedgerEntry.occurred_at.desc(), LedgerEntry.id.desc()).limit(PAGE_SIZE + 1)
    ).all()
    page = rows[:PAGE_SIZE]
    return LedgerPage(
        items=[LedgerItem(ref=e.public_ref, type=e.entry_type, amount_cents=e.amount_cents,  # type: ignore[arg-type]
                          occurred_at=iso(e.occurred_at) or "") for e in page],
        next_cursor=_encode_cursor(page[-1]) if len(rows) > PAGE_SIZE else None,
    )
