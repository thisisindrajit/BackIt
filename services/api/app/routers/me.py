from fastapi import APIRouter
from sqlalchemy import select

from app.deps import CurrentUserDep, DBDep
from app.models import Backing, Campaign, Product
from app.presenters import backing_out, profile_out
from app.schemas import (
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
    summaries = []
    for p in products:
        c = campaign_for_product(db, p.id)
        summaries.append(ProductSummary(
            id=p.id, name=p.name, slug=p.slug,
            campaign=CampaignRef(id=c.id, slug=c.slug, status=c.status, headline=c.headline)  # type: ignore[arg-type]
            if c else None,
        ))
    rows = db.execute(
        select(Backing, Campaign)
        .join(Campaign, Campaign.id == Backing.campaign_id)
        .where(Backing.user_id == user.id)
        .order_by(Backing.created_at)
    ).all()
    backings = [
        BackingSummary(id=b.id, campaign_slug=c.slug, campaign_headline=c.headline,
                       badge_number=b.badge_number, kind=b.kind)  # type: ignore[arg-type]
        for b, c in rows
    ]
    return Me(profile=profile_out(user), products=summaries, backings=backings)


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
