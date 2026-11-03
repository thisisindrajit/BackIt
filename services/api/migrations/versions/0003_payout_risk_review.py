"""AI-assisted risk review stored on payout previews

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-03 10:10:00

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payout_previews",
        sa.Column("risk_review", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        schema="app",
    )
    op.add_column("payout_previews", sa.Column("risk_source", sa.String(length=16), nullable=True), schema="app")


def downgrade() -> None:
    op.drop_column("payout_previews", "risk_source", schema="app")
    op.drop_column("payout_previews", "risk_review", schema="app")
