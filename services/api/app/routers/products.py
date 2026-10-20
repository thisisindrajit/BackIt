from fastapi import APIRouter, status

from app.deps import CurrentUserDep, DBDep, PayPalDep
from app.presenters import delivery_out, product_out, seller_out, verification_out
from app.schemas import (
    CampaignDraft,
    CampaignDraftIn,
    DemoVerificationIn,
    OnboardingOut,
    ProductCreate,
    ProductCreated,
    ProductOut,
    ProductUpdate,
    SellerConnectionOut,
    VerificationOut,
    WebhookDeliveryOut,
    WebhookSecretOut,
)
from app.services import campaigns as campaign_service
from app.services import products as product_service
from app.services.common import owned_product
from app.services.deliveries import deliver_now
from app.webhooks_out import enqueue_event

router = APIRouter(prefix="/products", tags=["products"])


@router.post("", status_code=status.HTTP_201_CREATED)
def create_product(body: ProductCreate, user: CurrentUserDep, db: DBDep) -> ProductCreated:
    product, secret = product_service.create_product(db, user, body)
    return ProductCreated(**product_out(db, product).model_dump(), webhook_secret=secret)


@router.get("/{product_id}")
def get_product(product_id: str, user: CurrentUserDep, db: DBDep) -> ProductOut:
    return product_out(db, owned_product(db, product_id, user))


@router.patch("/{product_id}")
def update_product(product_id: str, body: ProductUpdate, user: CurrentUserDep, db: DBDep) -> ProductOut:
    product = owned_product(db, product_id, user, lock=True)
    return product_out(db, product_service.update_product(db, user, product, body))


@router.post("/{product_id}/webhook-secret/rotate")
def rotate_webhook_secret(product_id: str, user: CurrentUserDep, db: DBDep) -> WebhookSecretOut:
    product = owned_product(db, product_id, user, lock=True)
    return WebhookSecretOut(webhook_secret=product_service.rotate_secret(db, user, product))


@router.post("/{product_id}/paypal/onboarding")
def start_paypal_onboarding(
    product_id: str, user: CurrentUserDep, db: DBDep, paypal: PayPalDep
) -> OnboardingOut:
    product = owned_product(db, product_id, user, lock=True)
    conn = product_service.start_onboarding(db, user, product, paypal)
    return OnboardingOut(status=conn.status, action_url=conn.action_url)  # type: ignore[arg-type]


@router.get("/{product_id}/paypal/status")
def get_paypal_status(
    product_id: str, user: CurrentUserDep, db: DBDep, paypal: PayPalDep
) -> SellerConnectionOut:
    product = owned_product(db, product_id, user)
    return seller_out(product_service.refresh_status(db, product, paypal))


@router.post("/{product_id}/verification/demo")
def record_demo_verification(
    product_id: str, body: DemoVerificationIn, user: CurrentUserDep, db: DBDep
) -> VerificationOut:
    product = owned_product(db, product_id, user)
    verification = product_service.demo_verification(db, user, product, body.months)
    out = verification_out(verification)
    assert out is not None
    return out


@router.post("/{product_id}/webhook-test")
def send_webhook_test(product_id: str, user: CurrentUserDep, db: DBDep) -> WebhookDeliveryOut:
    product = owned_product(db, product_id, user)
    delivery = enqueue_event(db, product, "ping", {
        "product_id": product.id,
        "message": "BackIt webhook test",
    })
    db.commit()
    delivery = deliver_now(db, delivery.id) or delivery
    return delivery_out(delivery)


@router.post("/{product_id}/campaign-draft")
def draft_campaign(
    product_id: str, body: CampaignDraftIn, user: CurrentUserDep, db: DBDep
) -> CampaignDraft:
    product = owned_product(db, product_id, user)
    return campaign_service.generate_draft(db, user, product, body.source_text)
