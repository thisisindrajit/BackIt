import base64
import hashlib
import hmac
import secrets

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings


def _fernet() -> Fernet:
    seed = get_settings().encryption_seed().encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(b"backit:webhook-secrets:" + seed).digest())
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_secret(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Unable to decrypt stored secret") from exc


def new_webhook_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)


def public_ref(*parts: str, prefix: str = "tx") -> str:
    """Stable pseudonymous reference that cannot be reversed to internal ids."""
    pepper = hashlib.sha256(b"backit:public-ref:" + get_settings().encryption_seed().encode())
    digest = hmac.new(pepper.digest(), ":".join(parts).encode(), hashlib.sha256).hexdigest()
    return f"{prefix}_{digest[:10]}"


def sha256_hex(data: bytes | str) -> str:
    if isinstance(data, str):
        data = data.encode()
    return hashlib.sha256(data).hexdigest()


def mask_email(email: str | None) -> str:
    if not email or "@" not in email:
        return "hidden"
    local, _, domain = email.partition("@")
    head = local[:1] if local else ""
    return f"{head}***@{domain}"
