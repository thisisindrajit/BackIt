"""Idempotency-Key handling for mutating financial calls."""

import json
from collections.abc import Callable
from typing import Any

from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import AppError, request_id_var
from app.ids import new_id
from app.models import IdempotencyKey
from app.security import sha256_hex


def _hash_request(body: Any) -> str:
    return sha256_hex(json.dumps(jsonable_encoder(body), sort_keys=True, separators=(",", ":")))


def run_idempotent(
    db: Session,
    *,
    user_id: str,
    scope: str,
    key: str | None,
    body: Any,
    action: Callable[[], tuple[int, BaseModel]],
) -> JSONResponse:
    """Run `action` once per (user, scope, key); replay the stored response afterwards."""
    if key is not None:
        key = key.strip()
        if not key or len(key) > 255:
            raise AppError(422, "invalid_idempotency_key", "Idempotency-Key must be 1-255 characters")
        request_hash = _hash_request(body)
        existing = db.scalars(
            select(IdempotencyKey).where(
                IdempotencyKey.user_id == user_id,
                IdempotencyKey.scope == scope,
                IdempotencyKey.key == key,
            )
        ).first()
        if existing is not None:
            if existing.request_hash != request_hash:
                raise AppError(
                    409, "idempotency_key_reused",
                    "This Idempotency-Key was already used with a different request",
                )
            return JSONResponse(
                status_code=existing.response_status,
                content=existing.response_body,
                headers={"Idempotent-Replayed": "true", "X-Request-ID": request_id_var.get()},
            )
    status_code, model = action()
    content = jsonable_encoder(model)
    # Uncertain (202) outcomes are not stored so a retry re-checks the provider.
    if key is not None and status_code != 202:
        record = IdempotencyKey(
            id=new_id("idk"),
            user_id=user_id,
            scope=scope,
            key=key,
            request_hash=request_hash,
            response_status=status_code,
            response_body=content,
        )
        db.add(record)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
    return JSONResponse(status_code=status_code, content=content)
