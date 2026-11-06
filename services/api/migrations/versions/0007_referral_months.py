"""Referred friends prepay months of the regular monthly plan

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-08 10:00:00.000000

"""
from collections.abc import Sequence
from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, Sequence[str], None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('campaigns', sa.Column('referral_months', sa.Integer(), server_default='12', nullable=False),
                  schema='app')
    # The regular price used to be a one-time price; spread it over 12 months so friends pay about the same.
    op.execute("UPDATE app.campaigns SET referral_months = 1 WHERE referral_list_price_cents < 1200")
    op.execute(
        "UPDATE app.campaigns SET referral_list_price_cents = ROUND(referral_list_price_cents / 12.0) "
        "WHERE referral_months = 12"
    )
    op.create_check_constraint(op.f("ck_campaigns_referral_months_range"), "campaigns",
                               "referral_months BETWEEN 1 AND 36", schema="app")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f("ck_campaigns_referral_months_range"), "campaigns", type_="check", schema="app")
    op.execute("UPDATE app.campaigns SET referral_list_price_cents = referral_list_price_cents * referral_months")
    op.drop_column('campaigns', 'referral_months', schema='app')
