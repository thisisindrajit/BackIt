from fastapi import APIRouter, status

from app.deps import CurrentUserDep, DBDep, IdempotencyKeyHeader, PayPalDep
from app.presenters import campaign_out, order_out
from app.schemas import CampaignCreate, CampaignOut, CampaignUpdate, OrderCreate, OrderOut, Readiness
from app.services import campaigns as campaign_service
from app.services import checkout
from app.services.common import owned_campaign, owned_product
from app.services.idempotency import run_idempotent

router = APIRouter(prefix="/campaigns", tags=["campaigns"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_campaign(body: CampaignCreate, user: CurrentUserDep, db: DBDep) -> CampaignOut:
    product = owned_product(db, body.product_id, user, lock=True)
    return campaign_out(campaign_service.create_campaign(db, user, product, body))


@router.get("/{campaign_id}")
def get_campaign(campaign_id: str, user: CurrentUserDep, db: DBDep) -> CampaignOut:
    campaign, _ = owned_campaign(db, campaign_id, user)
    return campaign_out(campaign)


@router.patch("/{campaign_id}")
def update_campaign(
    campaign_id: str, body: CampaignUpdate, user: CurrentUserDep, db: DBDep
) -> CampaignOut:
    campaign, _ = owned_campaign(db, campaign_id, user, lock=True)
    return campaign_out(campaign_service.update_campaign(db, user, campaign, body))


@router.get("/{campaign_id}/readiness")
def get_readiness(campaign_id: str, user: CurrentUserDep, db: DBDep) -> Readiness:
    campaign, product = owned_campaign(db, campaign_id, user)
    return campaign_service.readiness(db, campaign, product)


@router.post("/{campaign_id}/publish")
def publish_campaign(campaign_id: str, user: CurrentUserDep, db: DBDep) -> CampaignOut:
    campaign, product = owned_campaign(db, campaign_id, user, lock=True)
    return campaign_out(campaign_service.publish(db, user, campaign, product))


@router.post("/{campaign_id}/orders", status_code=status.HTTP_201_CREATED)
def create_order(
    campaign_id: str,
    body: OrderCreate,
    user: CurrentUserDep,
    db: DBDep,
    paypal: PayPalDep,
    idempotency_key: IdempotencyKeyHeader = None,
) -> OrderOut:
    def action() -> tuple[int, OrderOut]:
        order = checkout.create_order(db, user, campaign_id, body, paypal)
        return 201, order_out(db, order)

    return run_idempotent(  # type: ignore[return-value]
        db, user_id=user.id, scope=f"order_create:{campaign_id}", key=idempotency_key,
        body=body.model_dump(), action=action,
    )
