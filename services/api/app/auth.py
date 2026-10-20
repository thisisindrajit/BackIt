"""Bearer JWT verification against Better Auth's JWKS endpoint."""

import logging
from functools import lru_cache
from typing import Annotated, Any, Protocol

import jwt
from fastapi import Depends, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import DBDep
from app.errors import AppError
from app.models import Profile

logger = logging.getLogger("backit.auth")


class SigningKeySource(Protocol):
    def get_signing_key_from_jwt(self, token: str) -> Any: ...


@lru_cache
def _jwk_client() -> jwt.PyJWKClient:
    settings = get_settings()
    # PyJWKClient caches the key set and refetches once when a kid is unknown.
    return jwt.PyJWKClient(
        settings.auth_jwks_url, cache_keys=True, lifespan=300, timeout=5
    )


def get_key_source() -> SigningKeySource:
    return _jwk_client()


KeySourceDep = Annotated[SigningKeySource, Depends(get_key_source)]


def _unauthorized(message: str = "Authentication required") -> AppError:
    return AppError(401, "unauthorized", message)


def decode_token(token: str, key_source: SigningKeySource) -> dict[str, Any]:
    settings = get_settings()
    try:
        signing_key = key_source.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=settings.jwt_algorithms,
            audience=settings.jwt_audience,
            issuer=settings.auth_issuer,
            options={"require": ["exp", "sub"]},
            leeway=10,
        )
    except jwt.PyJWKClientError as exc:
        logger.warning("JWKS lookup failed: %s", exc)
        raise _unauthorized("Unable to verify token signing key") from exc
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise _unauthorized("Invalid token") from exc


def upsert_profile(db: Session, claims: dict[str, Any]) -> Profile:
    sub = str(claims["sub"])
    email = str(claims.get("email") or "")
    name = str(claims.get("name") or "").strip() or (email.split("@")[0] if email else "Backer")
    profile = db.get(Profile, sub)
    if profile is None:
        profile = Profile(
            id=sub,
            email=email,
            display_name=name[:120],
            payout_email=None,
            payout_email_verified=False,
            account_state="active",
        )
        db.add(profile)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            profile = db.get(Profile, sub)
            if profile is None:
                raise
    elif email and profile.email != email:
        profile.email = email
        db.commit()
    return profile


def get_current_user(request: Request, db: DBDep, key_source: KeySourceDep) -> Profile:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()
    claims = decode_token(token.strip(), key_source)
    profile = upsert_profile(db, claims)
    if profile.account_state != "active":
        raise AppError(403, "account_suspended", "This account is suspended")
    return profile


CurrentUserDep = Annotated[Profile, Depends(get_current_user)]
