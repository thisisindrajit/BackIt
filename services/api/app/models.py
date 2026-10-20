from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

SCHEMA = "app"

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(schema=SCHEMA, naming_convention=NAMING)
    type_annotation_map = {dict[str, Any]: JSONB, list[Any]: JSONB}


def _in(column: str, values: tuple[str, ...]) -> str:
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"


def _fk(target: str, ondelete: str | None = None) -> ForeignKey:
    return ForeignKey(f"{SCHEMA}.{target}", ondelete=ondelete)


def ForeignKeyAlter(target: str) -> ForeignKey:
    return ForeignKey(f"{SCHEMA}.{target}", use_alter=True)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Profile(TimestampMixin, Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(_in("account_state", ("active", "suspended")), name="account_state"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # Better Auth user id (sub)
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(120))
    payout_email: Mapped[str | None] = mapped_column(String(320))
    payout_email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    account_state: Mapped[str] = mapped_column(String(16), default="active")


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    owner_id: Mapped[str] = mapped_column(_fk("profiles.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    url: Mapped[str] = mapped_column(String(2048))
    description: Mapped[str] = mapped_column(Text)
    access_terms: Mapped[str] = mapped_column(Text)
    refund_terms: Mapped[str] = mapped_column(Text, default="")
    webhook_url: Mapped[str | None] = mapped_column(String(2048))
    webhook_secret_enc: Mapped[str] = mapped_column(Text)
    webhook_secret_hint: Mapped[str] = mapped_column(String(8))
    webhook_key_version: Mapped[int] = mapped_column(Integer, default=1)


class SellerConnection(TimestampMixin, Base):
    __tablename__ = "seller_connections"
    __table_args__ = (
        CheckConstraint(
            _in("status", ("not_connected", "pending", "connected", "failed")), name="status"
        ),
        CheckConstraint(_in("provider", ("mock", "paypal_sandbox")), name="provider"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(_fk("products.id", "CASCADE"), unique=True)
    owner_id: Mapped[str] = mapped_column(_fk("profiles.id"))
    provider: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="not_connected")
    merchant_id: Mapped[str | None] = mapped_column(String(64))
    tracking_id: Mapped[str] = mapped_column(String(64), unique=True)
    action_url: Mapped[str | None] = mapped_column(String(2048))
    payments_receivable: Mapped[bool] = mapped_column(Boolean, default=False)
    capabilities: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RevenueVerification(Base):
    __tablename__ = "revenue_verifications"
    __table_args__ = (
        CheckConstraint(_in("source", ("demo", "paypal", "stripe")), name="source"),
        CheckConstraint("threshold_cents >= 0", name="threshold_nonneg"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(_fk("products.id", "CASCADE"), index=True)
    source: Mapped[str] = mapped_column(String(16))
    is_demo: Mapped[bool] = mapped_column(Boolean)
    months: Mapped[list[Any]] = mapped_column(JSONB)
    threshold_cents: Mapped[int] = mapped_column(Integer)
    threshold_met: Mapped[bool] = mapped_column(Boolean)
    checked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Campaign(TimestampMixin, Base):
    __tablename__ = "campaigns"
    __table_args__ = (
        CheckConstraint(_in("status", ("draft", "published", "closed")), name="status"),
        CheckConstraint(
            "founding_price_cents BETWEEN 100 AND 1000000", name="founding_price_range"
        ),
        CheckConstraint(
            "referral_list_price_cents BETWEEN 100 AND 1000000", name="referral_price_range"
        ),
        CheckConstraint("referral_discount_bps BETWEEN 0 AND 5000", name="discount_bps_range"),
        CheckConstraint("commission_bps BETWEEN 0 AND 5000", name="commission_bps_range"),
        CheckConstraint("platform_fee_bps BETWEEN 0 AND 5000", name="platform_fee_bps_range"),
        CheckConstraint("founding_spots_cap BETWEEN 1 AND 10000", name="spots_cap_range"),
        CheckConstraint(
            "founding_spots_taken >= 0 AND founding_spots_taken <= founding_spots_cap",
            name="spots_taken_range",
        ),
        CheckConstraint("version >= 1", name="version_positive"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(_fk("products.id", "CASCADE"), unique=True)
    slug: Mapped[str] = mapped_column(String(40), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    version: Mapped[int] = mapped_column(Integer, default=1)
    headline: Mapped[str] = mapped_column(String(160))
    summary: Mapped[str] = mapped_column(Text)
    story: Mapped[str] = mapped_column(Text)
    founding_price_cents: Mapped[int] = mapped_column(Integer)
    founding_spots_cap: Mapped[int] = mapped_column(Integer)
    founding_spots_taken: Mapped[int] = mapped_column(Integer, default=0)
    referral_list_price_cents: Mapped[int] = mapped_column(Integer)
    referral_discount_bps: Mapped[int] = mapped_column(Integer)
    commission_bps: Mapped[int] = mapped_column(Integer)
    platform_fee_bps: Mapped[int] = mapped_column(Integer)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Order(TimestampMixin, Base):
    __tablename__ = "orders"
    __table_args__ = (
        CheckConstraint(_in("kind", ("founding", "referral")), name="kind"),
        CheckConstraint(
            _in(
                "state",
                ("created", "completed", "cancelled", "failed", "refunded", "pending_provider"),
            ),
            name="state",
        ),
        CheckConstraint(_in("provider", ("mock", "paypal_sandbox")), name="provider"),
        CheckConstraint(
            "list_price_cents >= 0 AND discount_cents >= 0 AND amount_cents > 0 "
            "AND platform_fee_cents >= 0 AND commission_cents >= 0",
            name="cents_nonneg",
        ),
        CheckConstraint("amount_cents = list_price_cents - discount_cents", name="amount_math"),
        CheckConstraint(
            "platform_fee_cents + commission_cents < amount_cents", name="fees_below_amount"
        ),
        CheckConstraint(
            "kind = 'founding' OR referrer_backing_id IS NOT NULL", name="referral_has_referrer"
        ),
        Index(
            "ix_orders_reservation_open",
            "campaign_id",
            "reservation_expires_at",
            postgresql_where=text("state = 'created' AND kind = 'founding'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(_fk("campaigns.id"), index=True)
    buyer_id: Mapped[str] = mapped_column(_fk("profiles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    state: Mapped[str] = mapped_column(String(20), default="created")
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    list_price_cents: Mapped[int] = mapped_column(Integer)
    discount_cents: Mapped[int] = mapped_column(Integer)
    amount_cents: Mapped[int] = mapped_column(Integer)
    platform_fee_cents: Mapped[int] = mapped_column(Integer)
    commission_cents: Mapped[int] = mapped_column(Integer)
    discount_bps: Mapped[int] = mapped_column(Integer)
    commission_bps: Mapped[int] = mapped_column(Integer)
    platform_fee_bps: Mapped[int] = mapped_column(Integer)
    referral_code: Mapped[str | None] = mapped_column(String(32))
    referrer_backing_id: Mapped[str | None] = mapped_column(ForeignKeyAlter("backings.id"))
    terms_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    provider: Mapped[str] = mapped_column(String(20))
    merchant_id: Mapped[str | None] = mapped_column(String(64))
    paypal_order_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    paypal_capture_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    payer_id: Mapped[str | None] = mapped_column(String(64))
    payer_email: Mapped[str | None] = mapped_column(String(320))
    approve_url: Mapped[str | None] = mapped_column(String(2048))
    reservation_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    backing_id: Mapped[str | None] = mapped_column(ForeignKeyAlter("backings.id"))
    failure_reason: Mapped[str | None] = mapped_column(Text)


class Backing(TimestampMixin, Base):
    __tablename__ = "backings"
    __table_args__ = (
        CheckConstraint(_in("kind", ("founding", "referral")), name="kind"),
        CheckConstraint(_in("status", ("active", "revoked")), name="status"),
        CheckConstraint(
            "(kind = 'founding' AND badge_number IS NOT NULL AND badge_number >= 1) "
            "OR (kind = 'referral' AND badge_number IS NULL)",
            name="badge_for_founding",
        ),
        UniqueConstraint("campaign_id", "badge_number"),
        Index(
            "uq_backings_founding_user",
            "campaign_id",
            "user_id",
            unique=True,
            postgresql_where=text("kind = 'founding'"),
        ),
        Index(
            "uq_backings_referral_user",
            "campaign_id",
            "user_id",
            unique=True,
            postgresql_where=text("kind = 'referral'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(_fk("campaigns.id"), index=True)
    user_id: Mapped[str] = mapped_column(_fk("profiles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(16))
    badge_number: Mapped[int | None] = mapped_column(Integer)
    referral_code: Mapped[str] = mapped_column(String(32), unique=True)
    status: Mapped[str] = mapped_column(String(16), default="active")
    order_id: Mapped[str] = mapped_column(ForeignKeyAlter("orders.id"), unique=True)


class Commission(TimestampMixin, Base):
    __tablename__ = "commissions"
    __table_args__ = (
        CheckConstraint(
            _in(
                "state",
                ("held", "payable", "reserved", "submitted", "paid", "reversed", "blocked"),
            ),
            name="state",
        ),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("currency = 'USD'", name="currency_usd"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    order_id: Mapped[str] = mapped_column(_fk("orders.id"), unique=True)
    backing_id: Mapped[str] = mapped_column(_fk("backings.id"), index=True)
    campaign_id: Mapped[str] = mapped_column(_fk("campaigns.id"), index=True)
    product_id: Mapped[str] = mapped_column(_fk("products.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    state: Mapped[str] = mapped_column(String(16), default="held")
    release_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    blocked_reason: Mapped[str | None] = mapped_column(String(64))
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Refund(TimestampMixin, Base):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint(_in("state", ("requested", "pending", "completed", "failed")), name="state"),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    order_id: Mapped[str] = mapped_column(_fk("orders.id"), unique=True)
    paypal_refund_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    capture_id: Mapped[str | None] = mapped_column(String(64))
    amount_cents: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(16), default="requested")
    requested_by: Mapped[str | None] = mapped_column(_fk("profiles.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text)


class PayoutPreview(Base):
    __tablename__ = "payout_previews"
    __table_args__ = (
        CheckConstraint(_in("status", ("open", "approved", "stale", "expired")), name="status"),
        CheckConstraint("total_cents >= 0", name="total_nonneg"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(_fk("products.id"), index=True)
    created_by: Mapped[str] = mapped_column(_fk("profiles.id"))
    status: Mapped[str] = mapped_column(String(16), default="open")
    digest: Mapped[str] = mapped_column(String(64))
    total_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    items: Mapped[list[Any]] = mapped_column(JSONB)
    exclusions: Mapped[list[Any]] = mapped_column(JSONB)
    funding: Mapped[dict[str, Any]] = mapped_column(JSONB)
    explanation_text: Mapped[str] = mapped_column(Text)
    explanation_source: Mapped[str] = mapped_column(String(16))
    ai_run_id: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class PayoutBatch(TimestampMixin, Base):
    __tablename__ = "payout_batches"
    __table_args__ = (
        CheckConstraint(
            _in(
                "status",
                ("queued", "submitted", "processing", "success", "partial", "failed"),
            ),
            name="status",
        ),
        CheckConstraint("total_cents > 0", name="total_positive"),
        CheckConstraint(_in("provider", ("mock", "paypal_sandbox")), name="provider"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(_fk("products.id"), index=True)
    preview_id: Mapped[str] = mapped_column(_fk("payout_previews.id"), unique=True)
    preview_digest: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="queued")
    provider: Mapped[str] = mapped_column(String(20))
    sender_batch_id: Mapped[str] = mapped_column(String(64), unique=True)
    provider_batch_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    total_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    funding_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str] = mapped_column(_fk("profiles.id"))
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    summary: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)


class PayoutItem(TimestampMixin, Base):
    __tablename__ = "payout_items"
    __table_args__ = (
        CheckConstraint(
            _in(
                "status",
                ("queued", "submitted", "pending", "success", "unclaimed", "failed", "returned"),
            ),
            name="status",
        ),
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        UniqueConstraint("batch_id", "backing_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    batch_id: Mapped[str] = mapped_column(_fk("payout_batches.id"), index=True)
    backing_id: Mapped[str] = mapped_column(_fk("backings.id"), index=True)
    receiver: Mapped[str] = mapped_column(String(320))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(16), default="queued")
    sender_item_id: Mapped[str] = mapped_column(String(64), unique=True)
    provider_item_id: Mapped[str | None] = mapped_column(String(64), unique=True)
    provider_status: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)


class PayoutAllocation(Base):
    __tablename__ = "payout_allocations"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        Index(
            "uq_payout_allocations_active_commission",
            "commission_id",
            unique=True,
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    payout_item_id: Mapped[str] = mapped_column(_fk("payout_items.id"), index=True)
    commission_id: Mapped[str] = mapped_column(_fk("commissions.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class ProviderEvent(Base):
    __tablename__ = "provider_events"
    __table_args__ = (
        CheckConstraint(
            _in("state", ("received", "processed", "failed", "ignored", "dead")), name="state"
        ),
        UniqueConstraint("provider", "provider_event_id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_event_id: Mapped[str] = mapped_column(String(128))
    event_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str | None] = mapped_column(String(128))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    verified: Mapped[bool] = mapped_column(Boolean)
    state: Mapped[str] = mapped_column(String(16), default="received")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutboxJob(TimestampMixin, Base):
    __tablename__ = "outbox_jobs"
    __table_args__ = (
        CheckConstraint(_in("state", ("pending", "running", "done", "dead")), name="state"),
        CheckConstraint("attempts >= 0", name="attempts_nonneg"),
        Index("ix_outbox_jobs_due", "state", "next_attempt_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    kind: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    dedupe_key: Mapped[str | None] = mapped_column(String(128), unique=True)
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=6)
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)


class WebhookDelivery(TimestampMixin, Base):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        CheckConstraint(
            _in("state", ("pending", "delivered", "failed", "dead")), name="state"
        ),
        CheckConstraint(
            _in("event_type", ("ping", "purchase.completed", "refund.issued")), name="event_type"
        ),
        Index("ix_webhook_deliveries_due", "state", "next_attempt_at"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(_fk("products.id", "CASCADE"), index=True)
    order_id: Mapped[str | None] = mapped_column(_fk("orders.id"), index=True)
    event_id: Mapped[str] = mapped_column(String(40), unique=True)
    event_type: Mapped[str] = mapped_column(String(40))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    target_url: Mapped[str | None] = mapped_column(String(2048))
    state: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=8)
    last_status_code: Mapped[int | None] = mapped_column(Integer)
    last_error: Mapped[str | None] = mapped_column(Text)
    response_excerpt: Mapped[str | None] = mapped_column(Text)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"
    __table_args__ = (
        CheckConstraint(
            _in(
                "entry_type",
                (
                    "founding_purchase",
                    "referral_purchase",
                    "refund",
                    "commission_earned",
                    "commission_reversed",
                    "payout_paid",
                ),
            ),
            name="entry_type",
        ),
        CheckConstraint("amount_cents >= 0", name="amount_nonneg"),
        Index("ix_ledger_entries_campaign_time", "campaign_id", "occurred_at", "id"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    campaign_id: Mapped[str] = mapped_column(_fk("campaigns.id"))
    entry_type: Mapped[str] = mapped_column(String(32))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    source_key: Mapped[str] = mapped_column(String(128), unique=True)
    public_ref: Mapped[str] = mapped_column(String(32))
    order_id: Mapped[str | None] = mapped_column(_fk("orders.id"))
    backing_id: Mapped[str | None] = mapped_column(_fk("backings.id"))
    commission_id: Mapped[str | None] = mapped_column(_fk("commissions.id"))
    payout_item_id: Mapped[str | None] = mapped_column(_fk("payout_items.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class RiskFlag(TimestampMixin, Base):
    __tablename__ = "risk_flags"
    __table_args__ = (
        CheckConstraint(_in("severity", ("low", "medium", "high")), name="severity"),
        CheckConstraint(_in("status", ("open", "cleared", "confirmed")), name="status"),
        UniqueConstraint("rule", "subject_key"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    product_id: Mapped[str] = mapped_column(_fk("products.id"), index=True)
    campaign_id: Mapped[str | None] = mapped_column(_fk("campaigns.id"))
    order_id: Mapped[str | None] = mapped_column(_fk("orders.id"))
    backing_id: Mapped[str | None] = mapped_column(_fk("backings.id"))
    commission_id: Mapped[str | None] = mapped_column(_fk("commissions.id"))
    rule: Mapped[str] = mapped_column(String(64))
    subject_key: Mapped[str] = mapped_column(String(128))
    severity: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(16), default="open")
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    explanation: Mapped[str | None] = mapped_column(Text)
    reviewer_id: Mapped[str | None] = mapped_column(_fk("profiles.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AiRun(Base):
    __tablename__ = "ai_runs"
    __table_args__ = (
        CheckConstraint(_in("source", ("ai", "template")), name="source"),
    )

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    purpose: Mapped[str] = mapped_column(String(40))
    actor_id: Mapped[str | None] = mapped_column(String(128))
    model: Mapped[str | None] = mapped_column(String(120))
    prompt_version: Mapped[str] = mapped_column(String(40))
    source: Mapped[str] = mapped_column(String(16))
    status: Mapped[str] = mapped_column(String(16))
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    error: Mapped[str | None] = mapped_column(Text)
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    actor_id: Mapped[str | None] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(80))
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[str] = mapped_column(String(64), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("user_id", "scope", "key"),)

    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(128))
    scope: Mapped[str] = mapped_column(String(120))
    key: Mapped[str] = mapped_column(String(255))
    request_hash: Mapped[str] = mapped_column(String(64))
    response_status: Mapped[int] = mapped_column(Integer)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
