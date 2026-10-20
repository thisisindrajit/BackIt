"""Outgoing builder webhooks: payload construction, HMAC signing, SSRF-safe delivery."""

import hashlib
import hmac
import ipaddress
import json
import logging
import random
import socket
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.ids import iso, new_id, utcnow
from app.models import Product, WebhookDelivery
from app.security import decrypt_secret

logger = logging.getLogger("backit.webhooks")

DEV_LOOPBACK_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
METADATA_HOSTS = frozenset({"metadata.google.internal", "metadata", "169.254.169.254"})


class UnsafeDestination(Exception):
    pass


def sign(secret: str, timestamp: int | str, raw_body: bytes) -> str:
    message = f"{timestamp}.".encode() + raw_body
    return "v1=" + hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def verify_signature(
    secret: str, timestamp: str, raw_body: bytes, signature: str, *, tolerance: int = 300,
    now: float | None = None,
) -> bool:
    try:
        ts = int(timestamp)
    except (TypeError, ValueError):
        return False
    current = time.time() if now is None else now
    if abs(current - ts) > tolerance:
        return False
    expected = sign(secret, ts, raw_body)
    return hmac.compare_digest(expected, signature)


def serialize_body(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()


def _ip_is_blocked(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
        return _ip_is_blocked(ip.ipv4_mapped)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or not ip.is_global
    )


def validate_destination(url: str, *, resolve: bool = True) -> None:
    """Raise UnsafeDestination unless url is a safe webhook target.

    Deployed: https only, and every resolved address must be public.
    Development: additionally allows http(s)://localhost / 127.0.0.1 / ::1.
    """
    settings = get_settings()
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if not host:
        raise UnsafeDestination("URL has no host")
    if parts.username or parts.password:
        raise UnsafeDestination("URL must not contain credentials")
    if host in METADATA_HOSTS or host.endswith(".internal"):
        raise UnsafeDestination("Cloud metadata endpoints are not allowed")
    dev_loopback = settings.is_development and host in DEV_LOOPBACK_HOSTS
    if parts.scheme == "https" or (parts.scheme == "http" and dev_loopback):
        pass
    else:
        raise UnsafeDestination("Webhook URL must use https")
    if dev_loopback:
        return
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        if _ip_is_blocked(literal):
            raise UnsafeDestination("Private, loopback, link-local or reserved addresses are blocked")
        return
    if not resolve:
        return
    try:
        infos = socket.getaddrinfo(host, parts.port or 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise UnsafeDestination(f"Host does not resolve: {host}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if _ip_is_blocked(ip):
            raise UnsafeDestination("Host resolves to a blocked address")


def build_event(event_type: str, data: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    event_id = new_id("evt")
    payload = {
        "id": event_id,
        "type": event_type,
        "version": 1,
        "created_at": iso(utcnow()),
        "data": data,
    }
    return event_id, payload


def enqueue_event(
    db: Session, product: Product, event_type: str, data: dict[str, Any],
    order_id: str | None = None,
) -> WebhookDelivery:
    event_id, payload = build_event(event_type, data)
    delivery = WebhookDelivery(
        id=new_id("dlv"),
        product_id=product.id,
        order_id=order_id,
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        target_url=product.webhook_url,
        state="pending",
        attempts=0,
        max_attempts=get_settings().webhook_max_attempts,
        next_attempt_at=utcnow(),
    )
    db.add(delivery)
    db.flush()
    return delivery


@dataclass
class AttemptResult:
    ok: bool
    status_code: int | None
    error: str | None
    excerpt: str | None


def send(url: str, secret: str, key_version: int, event_id: str, payload: dict[str, Any]) -> AttemptResult:
    settings = get_settings()
    try:
        validate_destination(url)
    except UnsafeDestination as exc:
        return AttemptResult(False, None, f"unsafe_destination: {exc}", None)
    body = serialize_body(payload)
    timestamp = int(time.time())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "BackIt-Webhooks/1",
        "BackIt-Event-Id": event_id,
        "BackIt-Timestamp": str(timestamp),
        "BackIt-Signature": sign(secret, timestamp, body),
        "BackIt-Key-Version": str(key_version),
    }
    try:
        with httpx.Client(
            timeout=httpx.Timeout(settings.webhook_timeout_seconds, connect=3.0),
            follow_redirects=False,
        ) as client, client.stream("POST", url, content=body, headers=headers) as resp:
            chunks = b""
            for chunk in resp.iter_bytes():
                chunks += chunk
                if len(chunks) >= settings.webhook_response_max_bytes:
                    break
            excerpt = chunks[: settings.webhook_response_max_bytes].decode("utf-8", "replace")
            ok = 200 <= resp.status_code < 300
            return AttemptResult(
                ok, resp.status_code, None if ok else f"HTTP {resp.status_code}", excerpt[:500]
            )
    except httpx.TimeoutException:
        return AttemptResult(False, None, "timeout", None)
    except httpx.HTTPError as exc:
        return AttemptResult(False, None, f"connection_error: {type(exc).__name__}", None)


def backoff_seconds(attempts: int) -> float:
    base = min(30 * (2 ** max(attempts - 1, 0)), 6 * 3600)
    return base * random.uniform(0.8, 1.2)


def attempt_delivery(db: Session, delivery: WebhookDelivery) -> WebhookDelivery:
    """Perform one attempt and record the outcome. Caller commits."""
    product = db.get(Product, delivery.product_id)
    now = utcnow()
    delivery.attempts += 1
    delivery.last_attempt_at = now
    delivery.lease_until = None
    url = product.webhook_url if product else None
    if not product or not url:
        result = AttemptResult(False, None, "no_webhook_url", None)
    else:
        delivery.target_url = url
        result = send(
            url, decrypt_secret(product.webhook_secret_enc), product.webhook_key_version,
            delivery.event_id, delivery.payload,
        )
    delivery.last_status_code = result.status_code
    delivery.response_excerpt = result.excerpt
    if result.ok:
        delivery.state = "delivered"
        delivery.last_error = None
        delivery.delivered_at = now
        delivery.next_attempt_at = None
    elif delivery.attempts >= delivery.max_attempts:
        delivery.state = "dead"
        delivery.last_error = result.error
        delivery.next_attempt_at = None
    else:
        delivery.state = "failed"
        delivery.last_error = result.error
        delivery.next_attempt_at = now + timedelta(seconds=backoff_seconds(delivery.attempts))
    return delivery
