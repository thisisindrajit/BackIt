import re
import secrets
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.errors import AppError
from app.ids import new_id, utcnow
from app.models import Product, Profile, RevenueVerification, SellerConnection
from app.presenters import default_provider, seller_connection
from app.providers.paypal import PayPalProvider, ProviderError
from app.schemas import ProductCreate, ProductUpdate
from app.security import encrypt_secret, new_webhook_secret
from app.services.common import audit
from app.webhooks_out import UnsafeDestination, validate_destination

VERIFICATION_THRESHOLD_CENTS = 100_000


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "product"
    return slug


def _unique_product_slug(db: Session, name: str) -> str:
    base = _slugify(name)
    candidate = base
    while db.scalars(select(Product.id).where(Product.slug == candidate)).first():
        candidate = f"{base[:33]}-{secrets.token_hex(3)}"
    return candidate


def _check_webhook_url(url: str | None) -> str | None:
    if url is None:
        return None
    try:
        validate_destination(url, resolve=False)
    except UnsafeDestination as exc:
        raise AppError(422, "invalid_webhook_url", str(exc)) from exc
    return url


def create_product(db: Session, user: Profile, body: ProductCreate) -> tuple[Product, str]:
    secret = new_webhook_secret()
    product = Product(
        id=new_id("prod"),
        owner_id=user.id,
        name=body.name,
        slug=_unique_product_slug(db, body.name),
        url=str(body.url),
        description=body.description,
        access_terms=body.access_terms,
        refund_terms=body.refund_terms or "",
        webhook_url=_check_webhook_url(str(body.webhook_url) if body.webhook_url else None),
        webhook_secret_enc=encrypt_secret(secret),
        webhook_secret_hint=secret[-4:],
        webhook_key_version=1,
    )
    db.add(product)
    audit(db, actor_id=user.id, action="product.created", target_type="product", target_id=product.id)
    db.commit()
    return product, secret


def update_product(db: Session, user: Profile, product: Product, body: ProductUpdate) -> Product:
    data = body.model_dump(exclude_unset=True)
    for field in ("name", "description", "access_terms"):
        if field in data and data[field] is None:
            raise AppError(422, "validation_error", f"{field} cannot be null")
    if "url" in data:
        if data["url"] is None:
            raise AppError(422, "validation_error", "url cannot be null")
        product.url = str(data["url"])
    if "webhook_url" in data:
        product.webhook_url = _check_webhook_url(
            str(data["webhook_url"]) if data["webhook_url"] else None
        )
    for field in ("name", "description", "access_terms"):
        if field in data:
            setattr(product, field, data[field])
    if "refund_terms" in data:
        product.refund_terms = data["refund_terms"] or ""
    audit(db, actor_id=user.id, action="product.updated", target_type="product",
          target_id=product.id, details={"fields": sorted(data.keys())})
    db.commit()
    return product


def rotate_secret(db: Session, user: Profile, product: Product) -> str:
    secret = new_webhook_secret()
    product.webhook_secret_enc = encrypt_secret(secret)
    product.webhook_secret_hint = secret[-4:]
    product.webhook_key_version += 1
    audit(db, actor_id=user.id, action="product.webhook_secret_rotated", target_type="product",
          target_id=product.id, details={"key_version": product.webhook_key_version})
    db.commit()
    return secret


def _ensure_connection(db: Session, product: Product) -> SellerConnection:
    conn = seller_connection(db, product.id)
    if conn is None:
        conn = SellerConnection(
            id=new_id("sc"),
            product_id=product.id,
            owner_id=product.owner_id,
            provider=default_provider(),
            status="not_connected",
            tracking_id=new_id("trk", 16),
            capabilities={},
            payments_receivable=False,
        )
        db.add(conn)
        db.flush()
    return conn


def start_onboarding(db: Session, user: Profile, product: Product,
                     paypal: PayPalProvider) -> SellerConnection:
    conn = _ensure_connection(db, product)
    if conn.status == "connected":
        return conn
    return_url = (
        f"{get_settings().web_base_url.rstrip('/')}/builder/products/{product.id}/onboarding/return"
    )
    try:
        link = paypal.create_referral_link(tracking_id=conn.tracking_id, return_url=return_url)
    except ProviderError as exc:
        conn.status = "failed"
        conn.checked_at = utcnow()
        db.commit()
        raise AppError(502, "provider_error", "PayPal onboarding link could not be created",
                       {"provider_message": str(exc)}) from exc
    conn.provider = paypal.name
    conn.action_url = link.action_url
    conn.checked_at = utcnow()
    if link.status == "connected":
        conn.status = "connected"
        conn.merchant_id = link.merchant_id
        conn.payments_receivable = True
        conn.capabilities = {"provider": "mock", "payments_receivable": True}
    else:
        conn.status = "pending"
    audit(db, actor_id=user.id, action="seller.onboarding_started", target_type="product",
          target_id=product.id, details={"provider": conn.provider, "status": conn.status})
    db.commit()
    return conn


def refresh_status(db: Session, product: Product, paypal: PayPalProvider) -> SellerConnection | None:
    conn = seller_connection(db, product.id)
    if conn is None or conn.status == "not_connected":
        return conn
    try:
        status = paypal.merchant_status(tracking_id=conn.tracking_id, merchant_id=conn.merchant_id)
    except ProviderError as exc:
        raise AppError(502, "provider_error", "Could not check PayPal seller status",
                       {"provider_message": str(exc)}) from exc
    conn.status = status.status
    conn.merchant_id = status.merchant_id or conn.merchant_id
    conn.payments_receivable = status.payments_receivable
    conn.capabilities = status.capabilities
    conn.checked_at = utcnow()
    db.commit()
    return conn


def _last_complete_months(count: int, now: datetime) -> list[str]:
    year, month = now.year, now.month
    months: list[str] = []
    for _ in range(count):
        month -= 1
        if month == 0:
            month, year = 12, year - 1
        months.append(f"{year:04d}-{month:02d}")
    return list(reversed(months))


def demo_verification(db: Session, user: Profile, product: Product,
                      months: list[int]) -> RevenueVerification:
    now = utcnow()
    labels = _last_complete_months(3, now.astimezone(UTC))
    rows = [{"month": m, "revenue_cents": v} for m, v in zip(labels, months, strict=True)]
    verification = RevenueVerification(
        id=new_id("rv"),
        product_id=product.id,
        source="demo",
        is_demo=True,
        months=rows,
        threshold_cents=VERIFICATION_THRESHOLD_CENTS,
        threshold_met=all(v >= VERIFICATION_THRESHOLD_CENTS for v in months),
        checked_at=now,
    )
    db.add(verification)
    audit(db, actor_id=user.id, action="verification.demo_recorded", target_type="product",
          target_id=product.id, details={"months": rows, "is_demo": True})
    db.commit()
    return verification
