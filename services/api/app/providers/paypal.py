"""PayPal provider: a deterministic mock and a real sandbox REST implementation.

The sandbox implementation only ever talks to https://api-m.sandbox.paypal.com.
"""

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Literal, Protocol

import httpx

from app.config import Settings, get_settings
from app.money import cents_to_decimal_string, decimal_string_to_cents

logger = logging.getLogger("backit.paypal")

ProviderName = Literal["mock", "paypal_sandbox"]


class ProviderError(Exception):
    """A provider call failed. `uncertain` means the outcome is unknown (timeout, 5xx)."""

    def __init__(self, message: str, *, uncertain: bool = False, issue: str | None = None,
                 status_code: int | None = None) -> None:
        super().__init__(message)
        self.uncertain = uncertain
        self.issue = issue
        self.status_code = status_code


@dataclass
class CreatedOrder:
    paypal_order_id: str
    status: str
    approve_url: str | None


@dataclass
class CaptureResult:
    status: Literal["COMPLETED", "PENDING", "DECLINED", "FAILED"]
    paypal_order_id: str
    capture_id: str | None
    amount_cents: int | None
    currency: str | None
    payer_id: str | None
    payer_email: str | None
    merchant_id: str | None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class RefundResult:
    refund_id: str
    status: Literal["COMPLETED", "PENDING", "FAILED", "CANCELLED"]


@dataclass
class ReferralLink:
    action_url: str | None
    status: Literal["pending", "connected"]
    merchant_id: str | None


@dataclass
class MerchantStatus:
    status: Literal["not_connected", "pending", "connected", "failed"]
    merchant_id: str | None
    payments_receivable: bool
    capabilities: dict[str, Any]


@dataclass
class PayoutItemRequest:
    sender_item_id: str
    receiver: str
    amount_cents: int
    note: str


@dataclass
class PayoutItemResult:
    sender_item_id: str
    provider_item_id: str | None
    transaction_status: str
    error: str | None = None


@dataclass
class PayoutBatchResult:
    provider_batch_id: str
    batch_status: str
    items: list[PayoutItemResult]


class PayPalProvider(Protocol):
    name: ProviderName

    def create_order(self, *, order_id: str, merchant_id: str, amount_cents: int,
                     platform_fee_cents: int, description: str, return_url: str,
                     cancel_url: str) -> CreatedOrder: ...

    def capture_order(self, *, paypal_order_id: str, request_id: str,
                      buyer_email: str, buyer_id: str, amount_cents: int,
                      merchant_id: str | None) -> CaptureResult: ...

    def get_order_status(self, paypal_order_id: str) -> str: ...

    def refund_capture(self, *, capture_id: str, amount_cents: int,
                       request_id: str) -> RefundResult: ...

    def create_referral_link(self, *, tracking_id: str, return_url: str) -> ReferralLink: ...

    def merchant_status(self, *, tracking_id: str, merchant_id: str | None) -> MerchantStatus: ...

    def verify_webhook(self, headers: dict[str, str], event: dict[str, Any]) -> bool: ...

    def create_payout(self, *, sender_batch_id: str, items: list[PayoutItemRequest],
                      subject: str) -> PayoutBatchResult: ...

    def get_payout_batch(self, provider_batch_id: str,
                         sender_item_ids: list[str]) -> PayoutBatchResult: ...


def _short_hash(*parts: str, length: int = 10) -> str:
    return hashlib.sha256(":".join(parts).encode()).hexdigest()[:length].upper()


class MockPayPal:
    """No network calls. Every identifier is prefixed with MOCK so it is always labelled."""

    name: ProviderName = "mock"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def create_order(self, *, order_id: str, merchant_id: str, amount_cents: int,
                     platform_fee_cents: int, description: str, return_url: str,
                     cancel_url: str) -> CreatedOrder:
        return CreatedOrder(
            paypal_order_id=f"MOCKORDER-{_short_hash(order_id, length=14)}",
            status="CREATED",
            approve_url=None,
        )

    def capture_order(self, *, paypal_order_id: str, request_id: str,
                      buyer_email: str, buyer_id: str, amount_cents: int,
                      merchant_id: str | None) -> CaptureResult:
        return CaptureResult(
            status="COMPLETED",
            paypal_order_id=paypal_order_id,
            capture_id=f"MOCKCAPTURE-{_short_hash(paypal_order_id, length=14)}",
            amount_cents=amount_cents,
            currency="USD",
            payer_id=f"MOCKPAYER{_short_hash(buyer_id, length=8)}",
            payer_email=buyer_email,
            merchant_id=merchant_id,
            raw={"provider": "mock"},
        )

    def get_order_status(self, paypal_order_id: str) -> str:
        return "CREATED"

    def refund_capture(self, *, capture_id: str, amount_cents: int,
                       request_id: str) -> RefundResult:
        return RefundResult(refund_id=f"MOCKREFUND-{_short_hash(capture_id, length=14)}",
                            status="COMPLETED")

    def create_referral_link(self, *, tracking_id: str, return_url: str) -> ReferralLink:
        return ReferralLink(
            action_url=None,
            status="connected",
            merchant_id=f"MOCKMERCHANT{_short_hash(tracking_id, length=8)}",
        )

    def merchant_status(self, *, tracking_id: str, merchant_id: str | None) -> MerchantStatus:
        return MerchantStatus(
            status="connected",
            merchant_id=merchant_id or f"MOCKMERCHANT{_short_hash(tracking_id, length=8)}",
            payments_receivable=True,
            capabilities={"provider": "mock", "payments_receivable": True,
                          "primary_email_confirmed": True},
        )

    def verify_webhook(self, headers: dict[str, str], event: dict[str, Any]) -> bool:
        # Mock events can only be injected in development with an explicit mock signature.
        return (
            self.settings.is_development
            and headers.get("paypal-transmission-sig") == "mock"
        )

    def create_payout(self, *, sender_batch_id: str, items: list[PayoutItemRequest],
                      subject: str) -> PayoutBatchResult:
        return PayoutBatchResult(
            provider_batch_id=f"MOCKBATCH-{_short_hash(sender_batch_id, length=12)}",
            batch_status="SUCCESS",
            items=[
                PayoutItemResult(
                    sender_item_id=i.sender_item_id,
                    provider_item_id=f"MOCKITEM-{_short_hash(i.sender_item_id, length=12)}",
                    transaction_status="SUCCESS",
                )
                for i in items
            ],
        )

    def get_payout_batch(self, provider_batch_id: str,
                         sender_item_ids: list[str]) -> PayoutBatchResult:
        return PayoutBatchResult(
            provider_batch_id=provider_batch_id,
            batch_status="SUCCESS",
            items=[
                PayoutItemResult(
                    sender_item_id=s,
                    provider_item_id=f"MOCKITEM-{_short_hash(s, length=12)}",
                    transaction_status="SUCCESS",
                )
                for s in sender_item_ids
            ],
        )


class SandboxPayPal:
    name: ProviderName = "paypal_sandbox"

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        if not settings.paypal_client_id or not settings.paypal_client_secret:
            raise RuntimeError("PAYPAL_CLIENT_ID and PAYPAL_CLIENT_SECRET are required in sandbox mode")
        self.settings = settings
        self.base = settings.paypal_api_base
        self.client = client or httpx.Client(timeout=httpx.Timeout(20.0, connect=5.0))
        self._token: str | None = None
        self._token_expires = 0.0
        self._lock = threading.Lock()

    # ----- plumbing -----

    def _access_token(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._token_expires - 60:
                return self._token
            try:
                resp = self.client.post(
                    f"{self.base}/v1/oauth2/token",
                    data={"grant_type": "client_credentials"},
                    auth=(self.settings.paypal_client_id or "", self.settings.paypal_client_secret or ""),
                    headers={"Accept": "application/json"},
                )
            except httpx.HTTPError as exc:
                raise ProviderError(f"PayPal OAuth failed: {exc}", uncertain=False) from exc
            if resp.status_code != 200:
                raise ProviderError(f"PayPal OAuth failed with {resp.status_code}",
                                    status_code=resp.status_code)
            body = resp.json()
            self._token = body["access_token"]
            self._token_expires = time.monotonic() + int(body.get("expires_in", 300))
            return self._token

    def _request(self, method: str, path: str, *, json: Any = None,
                 headers: dict[str, str] | None = None,
                 params: dict[str, Any] | None = None) -> dict[str, Any]:
        hdrs = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
            "Prefer": "return=representation",
        }
        if self.settings.paypal_bn_code:
            hdrs["PayPal-Partner-Attribution-Id"] = self.settings.paypal_bn_code
        hdrs.update(headers or {})
        try:
            resp = self.client.request(method, f"{self.base}{path}", json=json,
                                       headers=hdrs, params=params)
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise ProviderError(f"PayPal request timed out: {exc}", uncertain=True) from exc
        except httpx.HTTPError as exc:
            raise ProviderError(f"PayPal request failed: {exc}", uncertain=True) from exc
        if resp.status_code >= 500:
            raise ProviderError(f"PayPal returned {resp.status_code}", uncertain=True,
                                status_code=resp.status_code)
        data: dict[str, Any] = {}
        if resp.content:
            try:
                data = resp.json()
            except ValueError:
                data = {}
        if resp.status_code >= 400:
            issue = None
            details = data.get("details") or []
            if details and isinstance(details, list):
                issue = details[0].get("issue")
            raise ProviderError(
                f"PayPal returned {resp.status_code}: {data.get('name') or ''} {issue or ''}".strip(),
                issue=issue or data.get("name"),
                status_code=resp.status_code,
            )
        return data

    # ----- orders -----

    def create_order(self, *, order_id: str, merchant_id: str, amount_cents: int,
                     platform_fee_cents: int, description: str, return_url: str,
                     cancel_url: str) -> CreatedOrder:
        unit: dict[str, Any] = {
            "reference_id": order_id,
            "custom_id": order_id,
            "invoice_id": order_id,
            "description": description[:127],
            "amount": {"currency_code": "USD", "value": cents_to_decimal_string(amount_cents)},
            "payee": {"merchant_id": merchant_id},
        }
        if platform_fee_cents > 0:
            unit["payment_instruction"] = {
                "disbursement_mode": "INSTANT",
                "platform_fees": [
                    {"amount": {"currency_code": "USD",
                                "value": cents_to_decimal_string(platform_fee_cents)}}
                ],
            }
        body = {
            "intent": "CAPTURE",
            "purchase_units": [unit],
            "payment_source": {
                "paypal": {
                    "experience_context": {
                        "return_url": return_url,
                        "cancel_url": cancel_url,
                        "user_action": "PAY_NOW",
                        "shipping_preference": "NO_SHIPPING",
                    }
                }
            },
        }
        data = self._request("POST", "/v2/checkout/orders", json=body,
                             headers={"PayPal-Request-Id": f"{order_id}-create"})
        approve = next(
            (link["href"] for link in data.get("links", [])
             if link.get("rel") in ("payer-action", "approve")),
            None,
        )
        return CreatedOrder(paypal_order_id=data["id"], status=data.get("status", "CREATED"),
                            approve_url=approve)

    @staticmethod
    def _parse_capture(data: dict[str, Any]) -> CaptureResult:
        unit = (data.get("purchase_units") or [{}])[0]
        captures = (unit.get("payments") or {}).get("captures") or []
        capture = captures[0] if captures else {}
        payer = data.get("payer") or {}
        amount = capture.get("amount") or {}
        cap_status = capture.get("status") or data.get("status") or "FAILED"
        status: Literal["COMPLETED", "PENDING", "DECLINED", "FAILED"]
        if cap_status == "COMPLETED":
            status = "COMPLETED"
        elif cap_status == "PENDING":
            status = "PENDING"
        elif cap_status in ("DECLINED",):
            status = "DECLINED"
        else:
            status = "FAILED"
        return CaptureResult(
            status=status,
            paypal_order_id=data.get("id", ""),
            capture_id=capture.get("id"),
            amount_cents=decimal_string_to_cents(amount["value"]) if amount.get("value") else None,
            currency=amount.get("currency_code"),
            payer_id=payer.get("payer_id"),
            payer_email=payer.get("email_address"),
            merchant_id=(unit.get("payee") or {}).get("merchant_id"),
            raw={"order_status": data.get("status"), "capture_status": cap_status,
                 "seller_receivable_breakdown": capture.get("seller_receivable_breakdown")},
        )

    def capture_order(self, *, paypal_order_id: str, request_id: str,
                      buyer_email: str, buyer_id: str, amount_cents: int,
                      merchant_id: str | None) -> CaptureResult:
        try:
            data = self._request("POST", f"/v2/checkout/orders/{paypal_order_id}/capture",
                                 json={}, headers={"PayPal-Request-Id": request_id})
        except ProviderError as exc:
            if exc.issue == "ORDER_ALREADY_CAPTURED":
                data = self._request("GET", f"/v2/checkout/orders/{paypal_order_id}")
            else:
                raise
        return self._parse_capture(data)

    def get_order_status(self, paypal_order_id: str) -> str:
        data = self._request("GET", f"/v2/checkout/orders/{paypal_order_id}")
        return str(data.get("status", "UNKNOWN"))

    def refund_capture(self, *, capture_id: str, amount_cents: int,
                       request_id: str) -> RefundResult:
        data = self._request(
            "POST", f"/v2/payments/captures/{capture_id}/refund",
            json={"amount": {"currency_code": "USD",
                             "value": cents_to_decimal_string(amount_cents)}},
            headers={"PayPal-Request-Id": request_id},
        )
        status = data.get("status", "PENDING")
        return RefundResult(refund_id=data["id"],
                            status=status if status in ("COMPLETED", "PENDING", "FAILED",
                                                        "CANCELLED") else "PENDING")

    # ----- onboarding -----

    def create_referral_link(self, *, tracking_id: str, return_url: str) -> ReferralLink:
        body = {
            "tracking_id": tracking_id,
            "operations": [{
                "operation": "API_INTEGRATION",
                "api_integration_preference": {
                    "rest_api_integration": {
                        "integration_method": "PAYPAL",
                        "integration_type": "THIRD_PARTY",
                        "third_party_details": {"features": ["PAYMENT", "REFUND", "PARTNER_FEE"]},
                    }
                },
            }],
            "products": ["EXPRESS_CHECKOUT"],
            "legal_consents": [{"type": "SHARE_DATA_CONSENT", "granted": True}],
            "partner_config_override": {"return_url": return_url},
        }
        data = self._request("POST", "/v2/customer/partner-referrals", json=body)
        action = next((link["href"] for link in data.get("links", [])
                       if link.get("rel") == "action_url"), None)
        return ReferralLink(action_url=action, status="pending", merchant_id=None)

    def merchant_status(self, *, tracking_id: str, merchant_id: str | None) -> MerchantStatus:
        partner = self.settings.paypal_partner_merchant_id
        if not partner:
            raise ProviderError("PAYPAL_PARTNER_MERCHANT_ID is not configured")
        if not merchant_id:
            try:
                found = self._request(
                    "GET", f"/v1/customer/partners/{partner}/merchant-integrations",
                    params={"tracking_id": tracking_id},
                )
            except ProviderError as exc:
                if exc.status_code == 404:
                    return MerchantStatus("pending", None, False, {})
                raise
            merchant_id = found.get("merchant_id")
            if not merchant_id:
                return MerchantStatus("pending", None, False, {})
        data = self._request(
            "GET", f"/v1/customer/partners/{partner}/merchant-integrations/{merchant_id}"
        )
        receivable = bool(data.get("payments_receivable"))
        email_ok = bool(data.get("primary_email_confirmed"))
        products = data.get("products") or []
        capabilities = {
            "payments_receivable": receivable,
            "primary_email_confirmed": email_ok,
            "products": [{"name": p.get("name"), "status": p.get("vetting_status")}
                         for p in products if isinstance(p, dict)],
            "oauth_integrations": data.get("oauth_integrations", []),
        }
        status: Literal["connected", "pending"] = (
            "connected" if receivable and email_ok else "pending"
        )
        return MerchantStatus(status, merchant_id, receivable, capabilities)

    # ----- webhooks -----

    def verify_webhook(self, headers: dict[str, str], event: dict[str, Any]) -> bool:
        if not self.settings.paypal_webhook_id:
            logger.warning("PAYPAL_WEBHOOK_ID not configured; rejecting webhook")
            return False
        body = {
            "auth_algo": headers.get("paypal-auth-algo"),
            "cert_url": headers.get("paypal-cert-url"),
            "transmission_id": headers.get("paypal-transmission-id"),
            "transmission_sig": headers.get("paypal-transmission-sig"),
            "transmission_time": headers.get("paypal-transmission-time"),
            "webhook_id": self.settings.paypal_webhook_id,
            "webhook_event": event,
        }
        if not all(body.values()):
            return False
        data = self._request("POST", "/v1/notifications/verify-webhook-signature", json=body)
        return data.get("verification_status") == "SUCCESS"

    # ----- payouts -----

    def create_payout(self, *, sender_batch_id: str, items: list[PayoutItemRequest],
                      subject: str) -> PayoutBatchResult:
        body = {
            "sender_batch_header": {
                "sender_batch_id": sender_batch_id,
                "email_subject": subject[:255],
                "email_message": "Your BackIt referral commission (PayPal sandbox).",
            },
            "items": [
                {
                    "recipient_type": "EMAIL",
                    "receiver": i.receiver,
                    "amount": {"value": cents_to_decimal_string(i.amount_cents), "currency": "USD"},
                    "note": i.note[:4000],
                    "sender_item_id": i.sender_item_id,
                }
                for i in items
            ],
        }
        data = self._request("POST", "/v1/payments/payouts", json=body)
        header = data.get("batch_header") or {}
        return PayoutBatchResult(
            provider_batch_id=header.get("payout_batch_id", ""),
            batch_status=header.get("batch_status", "PENDING"),
            items=[],
        )

    def get_payout_batch(self, provider_batch_id: str,
                         sender_item_ids: list[str]) -> PayoutBatchResult:
        data = self._request("GET", f"/v1/payments/payouts/{provider_batch_id}",
                             params={"fields": "batch_header,items", "page_size": 100})
        header = data.get("batch_header") or {}
        items = []
        for item in data.get("items") or []:
            err = item.get("errors") or {}
            items.append(PayoutItemResult(
                sender_item_id=(item.get("payout_item") or {}).get("sender_item_id", ""),
                provider_item_id=item.get("payout_item_id"),
                transaction_status=item.get("transaction_status", "PENDING"),
                error=err.get("name") if isinstance(err, dict) else None,
            ))
        return PayoutBatchResult(
            provider_batch_id=provider_batch_id,
            batch_status=header.get("batch_status", "PENDING"),
            items=items,
        )


@lru_cache
def _provider_singleton(mode: str) -> PayPalProvider:
    settings = get_settings()
    if mode == "sandbox":
        return SandboxPayPal(settings)
    return MockPayPal(settings)


def get_paypal() -> PayPalProvider:
    return _provider_singleton(get_settings().paypal_mode)
