"""One-time access codes a backer redeems inside the builder's own app."""

import hmac
import re
import secrets

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.ids import utcnow
from app.models import Backing, Campaign, Order, Product, Profile
from app.security import decrypt_secret
from app.services.common import audit

# Crockford base32: no I, L, O or U, so codes survive being read aloud or retyped.
CLAIM_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
CLAIM_LENGTH = 12
_STRIP = re.compile(r"[\s\-_]")
_CONFUSABLE = str.maketrans({"O": "0", "I": "1", "L": "1"})


def generate_claim_code(db: Session) -> str:
    while True:
        code = "".join(secrets.choice(CLAIM_ALPHABET) for _ in range(CLAIM_LENGTH))
        if not db.scalars(select(Backing.id).where(Backing.claim_code == code)).first():
            return code


def normalize_claim_code(raw: str) -> str:
    return _STRIP.sub("", raw).upper().translate(_CONFUSABLE)


def format_claim_code(code: str) -> str:
    return "-".join(code[i : i + 4] for i in range(0, len(code), 4))


def authenticate_product(db: Session, product_id: str, token: str | None) -> Product:
    product = db.get(Product, product_id)
    # Same error for unknown product and wrong secret so ids can't be probed.
    if product is None or not token or not hmac.compare_digest(decrypt_secret(product.webhook_secret_enc), token):
        raise AppError(401, "invalid_product_secret", "Product id or secret is not valid")
    return product


def redeem_claim(db: Session, product: Product, raw_code: str, user_ref: str) -> tuple[Backing, Order, str, bool]:
    code = normalize_claim_code(raw_code)
    backing = None
    if len(code) == CLAIM_LENGTH:
        backing = db.scalars(
            select(Backing)
            .join(Campaign, Campaign.id == Backing.campaign_id)
            .where(Backing.claim_code == code, Campaign.product_id == product.id)
            .with_for_update(of=Backing)
        ).first()
    if backing is None:
        raise AppError(404, "claim_code_not_found", "That code doesn’t match a purchase for this product")
    if backing.status != "active":
        raise AppError(410, "access_revoked", "This purchase was refunded, so the code no longer works")

    order = db.get(Order, backing.order_id)
    assert order is not None
    buyer = db.get(Profile, backing.user_id)
    email = buyer.email if buyer else ""

    if backing.claimed_at is not None:
        if backing.claimed_by != user_ref:
            raise AppError(409, "claim_code_used", "This code was already redeemed by another account")
        return backing, order, email, False

    backing.claimed_at = utcnow()
    backing.claimed_by = user_ref
    audit(db, actor_id=None, action="backing.claimed", target_type="backing", target_id=backing.id,
          details={"product_id": product.id, "user_ref": user_ref})
    db.commit()
    return backing, order, email, True
