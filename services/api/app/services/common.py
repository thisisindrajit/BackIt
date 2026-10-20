from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, forbidden, not_found, request_id_var
from app.ids import new_id
from app.models import AuditEvent, Campaign, Product, Profile


def audit(
    db: Session,
    *,
    actor_id: str | None,
    action: str,
    target_type: str,
    target_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    db.add(
        AuditEvent(
            id=new_id("aud"),
            actor_id=actor_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details or {},
            request_id=request_id_var.get(),
        )
    )


def owned_product(db: Session, product_id: str, user: Profile, *, lock: bool = False) -> Product:
    stmt = select(Product).where(Product.id == product_id)
    if lock:
        stmt = stmt.with_for_update()
    product = db.scalars(stmt).first()
    if product is None:
        raise not_found("Product")
    if product.owner_id != user.id:
        raise forbidden()
    return product


def owned_campaign(db: Session, campaign_id: str, user: Profile, *, lock: bool = False) -> tuple[Campaign, Product]:
    stmt = select(Campaign).where(Campaign.id == campaign_id)
    if lock:
        stmt = stmt.with_for_update()
    campaign = db.scalars(stmt).first()
    if campaign is None:
        raise not_found("Campaign")
    product = db.get(Product, campaign.product_id)
    if product is None or product.owner_id != user.id:
        raise forbidden()
    return campaign, product


def campaign_for_product(db: Session, product_id: str) -> Campaign | None:
    return db.scalars(select(Campaign).where(Campaign.product_id == product_id)).first()


def conflict(code: str, message: str, details: dict[str, Any] | None = None) -> AppError:
    return AppError(409, code, message, details)
