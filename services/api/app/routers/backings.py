from fastapi import APIRouter

from app.deps import CurrentUserDep, DBDep
from app.errors import forbidden, not_found
from app.models import Backing, Campaign, Product
from app.schemas import ShareDraftIn, ShareDraftsOut
from app.services.sharing import generate_share_drafts

router = APIRouter(prefix="/backings", tags=["backings"])


@router.post("/{backing_id}/share-drafts")
def create_share_drafts(
    backing_id: str, body: ShareDraftIn, user: CurrentUserDep, db: DBDep
) -> ShareDraftsOut:
    backing = db.get(Backing, backing_id)
    if backing is None:
        raise not_found("Backing")
    if backing.user_id != user.id:
        raise forbidden()
    campaign = db.get(Campaign, backing.campaign_id)
    assert campaign is not None
    product = db.get(Product, campaign.product_id)
    assert product is not None
    return generate_share_drafts(db, user, backing, campaign, product, body)
