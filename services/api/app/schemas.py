"""Public API schemas. Field names follow docs/api-contract.md exactly."""

import re
from typing import Annotated, Any, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field, HttpUrl

SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$")
RESERVED_SLUGS = frozenset(
    {
        "admin", "api", "app", "auth", "backit", "backings", "builder", "campaign",
        "campaigns", "checkout", "dashboard", "docs", "help", "login", "logout", "me",
        "new", "onboarding", "orders", "payouts", "pricing", "privacy", "products",
        "public", "settings", "signin", "signup", "sign-in", "sign-up", "static",
        "support", "terms", "webhooks", "www", "ledger", "about", "blog", "status",
    }
)


def _check_slug(value: str) -> str:
    if not SLUG_RE.match(value):
        raise ValueError("slug must be 3-40 lowercase letters, digits or hyphens")
    if value in RESERVED_SLUGS:
        raise ValueError("slug is reserved")
    return value


Slug = Annotated[str, AfterValidator(_check_slug)]
PriceCents = Annotated[int, Field(ge=100, le=1_000_000)]
RateBps = Annotated[int, Field(ge=0, le=5000)]
Spots = Annotated[int, Field(ge=1, le=10_000)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ---------- Config ----------


class PublicConfig(BaseModel):
    paypal_mode: Literal["mock", "sandbox"]
    paypal_client_id: str | None
    ai_enabled: bool
    platform_fee_bps: int
    hold_days: int
    payout_minimum_cents: int
    environment: Literal["development", "production"]


# ---------- Identity ----------


class ProfileOut(BaseModel):
    id: str
    email: str
    display_name: str
    payout_email: str | None
    payout_email_verified: bool


class CampaignRef(BaseModel):
    id: str
    slug: str
    status: Literal["draft", "published", "closed"]
    headline: str


class ProductSummary(BaseModel):
    id: str
    name: str
    slug: str
    campaign: CampaignRef | None


class BackingSummary(BaseModel):
    id: str
    campaign_slug: str
    campaign_headline: str
    badge_number: int | None
    kind: Literal["founding", "referral"]


class Me(BaseModel):
    profile: ProfileOut
    products: list[ProductSummary]
    backings: list[BackingSummary]


class ProfileUpdate(StrictModel):
    display_name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    payout_email: EmailStr | None = None


# ---------- Products ----------


class SellerConnectionOut(BaseModel):
    status: Literal["not_connected", "pending", "connected", "failed"]
    merchant_id: str | None
    provider: Literal["mock", "paypal_sandbox"]
    checked_at: str | None
    payments_receivable: bool


class VerificationMonth(BaseModel):
    month: str
    revenue_cents: int


class VerificationOut(BaseModel):
    source: Literal["demo", "paypal", "stripe"]
    is_demo: bool
    months: list[VerificationMonth]
    threshold_cents: int
    threshold_met: bool
    checked_at: str


class CampaignOut(BaseModel):
    id: str
    product_id: str
    slug: str
    status: Literal["draft", "published", "closed"]
    version: int
    headline: str
    summary: str
    story: str
    founding_price_cents: int
    founding_spots_cap: int
    founding_spots_taken: int
    referral_list_price_cents: int
    referral_discount_bps: int
    commission_bps: int
    platform_fee_bps: int
    published_at: str | None
    updated_at: str


class ProductOut(BaseModel):
    id: str
    name: str
    slug: str
    url: str
    description: str
    access_terms: str
    refund_terms: str
    webhook_url: str | None
    webhook_secret_hint: str | None
    seller: SellerConnectionOut
    verification: VerificationOut | None
    campaign: CampaignOut | None
    created_at: str


class ProductCreated(ProductOut):
    webhook_secret: str


class ProductCreate(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=120)]
    url: HttpUrl
    description: Annotated[str, Field(min_length=1, max_length=5000)]
    access_terms: Annotated[str, Field(min_length=1, max_length=2000)]
    refund_terms: Annotated[str, Field(max_length=2000)] | None = None
    webhook_url: HttpUrl | None = None


class ProductUpdate(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    url: HttpUrl | None = None
    description: Annotated[str, Field(min_length=1, max_length=5000)] | None = None
    access_terms: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    refund_terms: Annotated[str, Field(max_length=2000)] | None = None
    webhook_url: HttpUrl | None = None


class WebhookSecretOut(BaseModel):
    webhook_secret: str


class OnboardingOut(BaseModel):
    status: Literal["not_connected", "pending", "connected", "failed"]
    action_url: str | None


class DemoVerificationIn(StrictModel):
    months: Annotated[list[Annotated[int, Field(ge=0, le=1_000_000_000)]], Field(min_length=3, max_length=3)]


# ---------- Campaigns ----------


class CampaignDraftIn(StrictModel):
    source_text: Annotated[str, Field(max_length=8000)] | None = None


class CampaignDraft(BaseModel):
    headline: str
    summary: str
    story: str
    founding_price_cents: int
    founding_spots_cap: int
    referral_list_price_cents: int
    referral_discount_bps: int
    commission_bps: int
    disclosure: str
    missing_evidence: list[str]
    source: Literal["ai", "template"]
    ai_run_id: str | None


class CampaignCreate(StrictModel):
    product_id: str
    slug: Slug
    headline: Annotated[str, Field(min_length=1, max_length=160)]
    summary: Annotated[str, Field(min_length=1, max_length=1000)]
    story: Annotated[str, Field(min_length=1, max_length=10000)]
    founding_price_cents: PriceCents
    founding_spots_cap: Spots
    referral_list_price_cents: PriceCents
    referral_discount_bps: RateBps
    commission_bps: RateBps


class CampaignUpdate(StrictModel):
    slug: Slug | None = None
    headline: Annotated[str, Field(min_length=1, max_length=160)] | None = None
    summary: Annotated[str, Field(min_length=1, max_length=1000)] | None = None
    story: Annotated[str, Field(min_length=1, max_length=10000)] | None = None
    founding_price_cents: PriceCents | None = None
    founding_spots_cap: Spots | None = None
    referral_list_price_cents: PriceCents | None = None
    referral_discount_bps: RateBps | None = None
    commission_bps: RateBps | None = None


class ReadinessCheck(BaseModel):
    key: str
    label: str
    ok: bool
    detail: str | None


class Readiness(BaseModel):
    ready: bool
    checks: list[ReadinessCheck]


# ---------- Public ----------


class PublicProduct(BaseModel):
    name: str
    url: str


class PublicFounding(BaseModel):
    price_cents: int
    spots_cap: int
    spots_taken: int
    spots_left: int


class PublicReferral(BaseModel):
    list_price_cents: int
    discount_bps: int
    price_cents: int
    commission_bps: int
    commission_cents: int


class PublicTrust(BaseModel):
    verification: VerificationOut | None
    seller_connected: bool
    seller_provider: Literal["mock", "paypal_sandbox"]
    access_terms: str
    refund_terms: str
    hold_days: int
    payout_minimum_cents: int


class PublicStats(BaseModel):
    backers: int
    sales: int


class PublicReferrer(BaseModel):
    code: str
    display_name: str


class PublicCampaign(BaseModel):
    id: str
    slug: str
    headline: str
    summary: str
    story: str
    status: Literal["draft", "published", "closed"]
    product: PublicProduct
    builder_name: str
    founding: PublicFounding
    referral: PublicReferral
    platform_fee_bps: int
    trust: PublicTrust
    stats: PublicStats
    referrer: PublicReferrer | None


LedgerType = Literal[
    "founding_purchase",
    "referral_purchase",
    "refund",
    "commission_earned",
    "commission_reversed",
    "payout_paid",
]


class LedgerItem(BaseModel):
    ref: str
    type: LedgerType
    amount_cents: int
    occurred_at: str


class LedgerPage(BaseModel):
    items: list[LedgerItem]
    next_cursor: str | None


# ---------- Orders ----------


class OrderCreate(StrictModel):
    kind: Literal["founding", "referral"]
    referral_code: Annotated[str, Field(min_length=1, max_length=32)] | None = None


class OrderBacking(BaseModel):
    id: str
    badge_number: int | None
    referral_code: str
    share_url: str


class OrderAccess(BaseModel):
    status: Literal["pending", "delivered", "failed", "not_configured"]
    last_attempt_at: str | None


OrderState = Literal["created", "completed", "cancelled", "failed", "refunded", "pending_provider"]


class OrderOut(BaseModel):
    id: str
    campaign_id: str
    campaign_slug: str
    kind: Literal["founding", "referral"]
    state: OrderState
    list_price_cents: int
    discount_cents: int
    amount_cents: int
    platform_fee_cents: int
    commission_cents: int
    referral_code: str | None
    provider: Literal["mock", "paypal_sandbox"]
    paypal_order_id: str | None
    reservation_expires_at: str | None
    backing: OrderBacking | None
    access: OrderAccess
    created_at: str


# ---------- Backings ----------


class BackingCampaign(BaseModel):
    id: str
    slug: str
    headline: str
    product_name: str


class Balances(BaseModel):
    held_cents: int
    payable_cents: int
    reserved_cents: int
    paid_cents: int
    reversed_cents: int


CommissionState = Literal["held", "payable", "reserved", "submitted", "paid", "reversed", "blocked"]


class CommissionOut(BaseModel):
    id: str
    order_ref: str
    amount_cents: int
    state: CommissionState
    release_at: str
    created_at: str


class BackingOut(BaseModel):
    id: str
    kind: Literal["founding", "referral"]
    campaign: BackingCampaign
    badge_number: int | None
    referral_code: str
    share_url: str
    balances: Balances
    commissions: list[CommissionOut]
    created_at: str


class ShareDraftIn(StrictModel):
    channel: Literal["x", "linkedin", "email"]
    context: Annotated[str, Field(max_length=1000)] | None = None


class ShareDraft(BaseModel):
    channel: Literal["x", "linkedin", "email"]
    text: str


class ShareDraftsOut(BaseModel):
    drafts: list[ShareDraft]
    source: Literal["ai", "template"]


# ---------- Builder ----------


class SalesTotals(BaseModel):
    orders: int
    captured_cents: int
    refunded_cents: int
    platform_fee_cents: int
    commission_liability_cents: int
    commission_paid_cents: int


class SalesOrder(BaseModel):
    id: str
    kind: Literal["founding", "referral"]
    state: OrderState
    buyer_label: str
    referral_code: str | None
    amount_cents: int
    platform_fee_cents: int
    commission_cents: int
    created_at: str


class SalesSummary(BaseModel):
    totals: SalesTotals
    orders: list[SalesOrder]


class WebhookDeliveryOut(BaseModel):
    id: str
    event_id: str
    event_type: str
    state: Literal["pending", "delivered", "failed", "dead"]
    attempts: int
    last_status_code: int | None
    last_error: str | None
    next_attempt_at: str | None
    created_at: str


class RiskFlagOut(BaseModel):
    id: str
    rule: str
    severity: str
    status: str
    evidence: dict[str, Any]
    explanation: str | None
    created_at: str


# ---------- Payouts ----------


class PreviewItem(BaseModel):
    backing_id: str
    backer_name: str
    payout_email_masked: str
    amount_cents: int
    commission_ids: list[str]


ExclusionReason = Literal[
    "below_minimum", "in_hold", "no_payout_email", "risk_review", "refund_pending"
]


class PreviewExclusion(BaseModel):
    backing_id: str
    backer_name: str
    amount_cents: int
    reason: ExclusionReason


class Funding(BaseModel):
    source: Literal["sandbox_sender"]
    available_cents: int | None
    required_cents: int
    sufficient: bool | None


class Explanation(BaseModel):
    text: str
    source: Literal["ai", "template"]


class PayoutPreviewOut(BaseModel):
    id: str
    product_id: str
    status: Literal["open", "approved", "stale", "expired"]
    digest: str
    total_cents: int
    currency: Literal["USD"]
    items: list[PreviewItem]
    exclusions: list[PreviewExclusion]
    funding: Funding
    explanation: Explanation
    created_at: str
    expires_at: str


class ApproveIn(StrictModel):
    digest: Annotated[str, Field(min_length=1, max_length=64)]
    funding_confirmed: bool


class PayoutBatchItemOut(BaseModel):
    id: str
    backer_name: str
    amount_cents: int
    status: Literal["queued", "submitted", "pending", "success", "unclaimed", "failed", "returned"]
    provider_item_id: str | None


class PayoutBatchOut(BaseModel):
    id: str
    product_id: str
    preview_id: str
    status: Literal["queued", "submitted", "processing", "success", "partial", "failed"]
    sender_batch_id: str
    provider_batch_id: str | None
    total_cents: int
    items: list[PayoutBatchItemOut]
    approved_by: str
    approved_at: str
    summary: str | None


class ReleasedOut(BaseModel):
    released: int


class AckOut(BaseModel):
    received: bool
