"""Lower the revenue threshold to $100 a month and re-check stored evidence

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-03 20:05:00

"""
from collections.abc import Sequence

from alembic import op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _recheck(threshold: int) -> None:
    op.execute(f"""
        UPDATE app.revenue_verifications SET
          threshold_cents = {threshold},
          threshold_met = NOT EXISTS (
            SELECT 1 FROM jsonb_array_elements(months) m
            WHERE COALESCE((m->>'revenue_cents')::bigint, (m #>> '{{}}')::bigint) < {threshold}
          )
    """)


def upgrade() -> None:
    _recheck(10_000)


def downgrade() -> None:
    _recheck(100_000)
