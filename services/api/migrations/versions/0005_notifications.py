"""Notifications: in-app notices for sales and launches, with a Resend email outbox

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-04 19:40:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.String(length=40), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("dedupe_key", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("link", sa.String(length=512), nullable=True),
        sa.Column("campaign_id", sa.String(length=40), nullable=True),
        sa.Column("order_id", sa.String(length=40), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_to", sa.String(length=320), nullable=True),
        sa.Column("email_state", sa.String(length=16), nullable=False),
        sa.Column("email_attempts", sa.Integer(), nullable=False),
        sa.Column("email_next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_last_error", sa.Text(), nullable=True),
        sa.Column("email_message_id", sa.String(length=128), nullable=True),
        sa.Column("email_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("kind IN ('sale', 'referral_sale', 'campaign_live')", name=op.f("ck_notifications_kind")),
        sa.CheckConstraint(
            "email_state IN ('none', 'pending', 'sent', 'failed', 'dead', 'skipped')",
            name=op.f("ck_notifications_email_state"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app.profiles.id"], name=op.f("fk_notifications_user_id_profiles"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campaign_id"], ["app.campaigns.id"], name=op.f("fk_notifications_campaign_id_campaigns"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_id"], ["app.orders.id"], name=op.f("fk_notifications_order_id_orders"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notifications")),
        sa.UniqueConstraint("dedupe_key", name=op.f("uq_notifications_dedupe_key")),
        schema="app",
    )
    op.create_index("ix_notifications_user_id_created_at", "notifications", ["user_id", "created_at"], schema="app")
    op.create_index("ix_notifications_email_due", "notifications", ["email_state", "email_next_attempt_at"], schema="app")
    op.create_index(op.f("ix_notifications_campaign_id"), "notifications", ["campaign_id"], schema="app")
    op.create_index(op.f("ix_notifications_order_id"), "notifications", ["order_id"], schema="app")


def downgrade() -> None:
    op.drop_table("notifications", schema="app")
