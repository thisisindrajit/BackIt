from typing import Annotated

from fastapi import APIRouter, Header

from app.db import DBDep
from app.ids import iso
from app.models import Campaign
from app.presenters import offer_out
from app.schemas import ClaimRedeemIn, ClaimRedeemOut
from app.services.claims import authenticate_product, redeem_claim

router = APIRouter(prefix="/claims", tags=["claims"])


@router.post("/redeem")
def redeem(
    body: ClaimRedeemIn,
    db: DBDep,
    authorization: Annotated[str | None, Header()] = None,
) -> ClaimRedeemOut:
    """Server-to-server: the builder's backend redeems a backer's one-time code.

    Authenticate with `Authorization: Bearer <product webhook secret>`.
    """
    token = authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else None
    product = authenticate_product(db, body.product_id, token)
    backing, order, email, fresh = redeem_claim(db, product, body.code, body.user_ref)
    campaign = db.get(Campaign, order.campaign_id)
    assert campaign is not None
    return ClaimRedeemOut(
        status="redeemed" if fresh else "already_redeemed",
        order_id=order.id,
        plan_id=order.kind,  # type: ignore[arg-type]
        offer=offer_out(campaign, order.kind),
        badge_number=backing.badge_number,
        buyer_email=email,
        user_ref=backing.claimed_by or body.user_ref,
        claimed_at=iso(backing.claimed_at) or "",
    )
