from fastapi import APIRouter

from app.deps import CurrentUserDep, DBDep
from app.errors import forbidden, not_found
from app.models import Backing, Campaign, Product
from app.presenters import access_report_out
from app.schemas import AccessReportIn, AccessReportOut, ShareDraftIn, ShareDraftsOut
from app.services import access_reports
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


@router.post("/{backing_id}/access-report", status_code=201)
def report_access(backing_id: str, body: AccessReportIn, user: CurrentUserDep, db: DBDep) -> AccessReportOut:
    """Tell the builder the offer isn't working. Reward payouts pause until it's resolved or refunded."""
    out = access_report_out(access_reports.open_report(db, user, backing_id, body.message))
    assert out is not None
    return out


@router.post("/{backing_id}/access-report/resolve")
def resolve_access_report(backing_id: str, user: CurrentUserDep, db: DBDep) -> AccessReportOut:
    out = access_report_out(access_reports.resolve_report(db, user, backing_id))
    assert out is not None
    return out
