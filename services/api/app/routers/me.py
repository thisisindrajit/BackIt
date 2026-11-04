from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from app.deps import CurrentUserDep, DBDep
from app.ids import iso, utcnow
from app.models import (
    Backing,
    Campaign,
    Commission,
    Order,
    PayoutBatch,
    PayoutItem,
    Product,
    Profile,
)
from app.presenters import backing_out, profile_out
from app.schemas import (
    Activity,
    ActivityTotals,
    ActivityWeek,
    BackingOut,
    BackingSummary,
    CampaignRef,
    Me,
    ProductSummary,
    ProfileOut,
    ProfileUpdate,
)
from app.services.common import audit, campaign_for_product

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def get_me(user: CurrentUserDep, db: DBDep) -> Me:
    products = db.scalars(
        select(Product).where(Product.owner_id == user.id).order_by(Product.created_at)
    ).all()
    campaigns = {p.id: campaign_for_product(db, p.id) for p in products}
    campaign_ids = [c.id for c in campaigns.values() if c]
    referral_counts = dict(db.execute(
        select(Backing.campaign_id, func.count(Backing.id))
        .where(Backing.campaign_id.in_(campaign_ids), Backing.kind == "referral", Backing.status == "active")
        .group_by(Backing.campaign_id)
    ).all()) if campaign_ids else {}
    summaries = []
    for p in products:
        c = campaigns[p.id]
        summaries.append(ProductSummary(
            id=p.id, name=p.name, slug=p.slug, description=p.description,
            created_at=iso(p.created_at) or "",
            campaign=CampaignRef(
                id=c.id, slug=c.slug, status=c.status, headline=c.headline,  # type: ignore[arg-type]
                founding_price_cents=c.founding_price_cents, spots_cap=c.founding_spots_cap,
                spots_taken=c.founding_spots_taken, referral_buyers=referral_counts.get(c.id, 0),
                published_at=iso(c.published_at),
            ) if c else None,
        ))
    rows = db.execute(
        select(Backing, Campaign, Product.name, Profile.display_name)
        .join(Campaign, Campaign.id == Backing.campaign_id)
        .join(Product, Product.id == Campaign.product_id)
        .outerjoin(Profile, Profile.id == Product.owner_id)
        .where(Backing.user_id == user.id)
        .order_by(Backing.created_at)
    ).all()
    earned = func.coalesce(func.sum(Commission.amount_cents), 0)
    stats = {
        backing_id: (int(count), int(total))
        for backing_id, count, total in db.execute(
            select(Commission.backing_id, func.count(Commission.id), earned)
            .where(Commission.backing_id.in_([b.id for b, *_ in rows]),
                   Commission.state.not_in(("reversed", "blocked")))
            .group_by(Commission.backing_id)
        ).all()
    } if rows else {}
    backings = [
        BackingSummary(
            id=b.id, campaign_slug=c.slug, campaign_headline=c.headline,
            product_name=product_name, builder_name=builder_name or "Builder",
            badge_number=b.badge_number, kind=b.kind,  # type: ignore[arg-type]
            referrals=stats.get(b.id, (0, 0))[0], earned_cents=stats.get(b.id, (0, 0))[1],
            backed_at=iso(b.created_at) or "",
        )
        for b, c, product_name, builder_name in rows
    ]
    return Me(profile=profile_out(user), products=summaries, backings=backings)


@router.get("/activity")
def get_activity(
    user: CurrentUserDep, db: DBDep, weeks: Annotated[int, Query(ge=4, le=52)] = 12
) -> Activity:
    """Weekly money in and out: sales of your campaigns, rewards you earned, rewards you paid."""
    today = utcnow().date()
    first = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    since = datetime.combine(first, datetime.min.time(), tzinfo=utcnow().tzinfo)
    buckets = {first + timedelta(weeks=i): [0, 0, 0] for i in range(weeks)}

    def add(series: int, rows: Sequence[Any]) -> None:
        for at, cents in rows:
            if at is None:
                continue
            d: date = at.date()
            buckets[d - timedelta(days=d.weekday())][series] += cents

    add(0, db.execute(
        select(Order.completed_at, Order.amount_cents)
        .join(Campaign, Campaign.id == Order.campaign_id)
        .join(Product, Product.id == Campaign.product_id)
        .where(Product.owner_id == user.id, Order.state == "completed",
               Order.completed_at >= since)
    ).all())
    add(1, db.execute(
        select(Commission.created_at, Commission.amount_cents)
        .join(Backing, Backing.id == Commission.backing_id)
        .where(Backing.user_id == user.id, Commission.state.not_in(("reversed", "blocked")),
               Commission.created_at >= since)
    ).all())
    add(2, db.execute(
        select(PayoutItem.updated_at, PayoutItem.amount_cents)
        .join(PayoutBatch, PayoutBatch.id == PayoutItem.batch_id)
        .join(Product, Product.id == PayoutBatch.product_id)
        .where(Product.owner_id == user.id, PayoutItem.status == "success",
               PayoutItem.updated_at >= since)
    ).all())

    rows = [ActivityWeek(week=w.isoformat(), sales_cents=v[0], earned_cents=v[1], sent_cents=v[2])
            for w, v in buckets.items()]
    return Activity(weeks=rows, totals=ActivityTotals(
        sales_cents=sum(r.sales_cents for r in rows),
        earned_cents=sum(r.earned_cents for r in rows),
        sent_cents=sum(r.sent_cents for r in rows),
    ))


@router.patch("")
def update_me(body: ProfileUpdate, user: CurrentUserDep, db: DBDep) -> ProfileOut:
    if body.display_name is not None:
        user.display_name = body.display_name.strip()
    if "payout_email" in body.model_fields_set:
        new_email = body.payout_email.strip().lower() if body.payout_email else None
        if new_email != user.payout_email:
            user.payout_email = new_email
            user.payout_email_verified = new_email is not None
            if new_email:
                audit(db, actor_id=user.id, action="payout_email.sandbox_verified",
                      target_type="profile", target_id=user.id,
                      details={"verification": "sandbox_auto_verified",
                               "note": "Sandbox only: payout email marked verified without a "
                                       "confirmation round-trip."})
            else:
                audit(db, actor_id=user.id, action="payout_email.cleared",
                      target_type="profile", target_id=user.id)
    db.commit()
    return profile_out(user)


@router.get("/backings")
def list_my_backings(user: CurrentUserDep, db: DBDep) -> list[BackingOut]:
    backings = db.scalars(
        select(Backing).where(Backing.user_id == user.id).order_by(Backing.created_at)
    ).all()
    return [backing_out(db, b) for b in backings]
