from typing import Annotated

from fastapi import Depends, Header

from app.auth import CurrentUserDep
from app.db import DBDep
from app.providers.paypal import PayPalProvider, get_paypal

PayPalDep = Annotated[PayPalProvider, Depends(get_paypal)]
IdempotencyKeyHeader = Annotated[
    str | None,
    Header(alias="Idempotency-Key", description="Optional key; replays the first response."),
]

__all__ = ["CurrentUserDep", "DBDep", "IdempotencyKeyHeader", "PayPalDep"]
