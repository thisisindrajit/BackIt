import secrets
from datetime import UTC, datetime

_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"


def new_id(prefix: str, length: int = 20) -> str:
    return f"{prefix}_" + "".join(secrets.choice(_ALPHABET) for _ in range(length))


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
