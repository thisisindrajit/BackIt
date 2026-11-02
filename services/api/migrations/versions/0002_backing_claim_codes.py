"""one-time access claim codes on backings

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29 21:50:00

"""
import secrets
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def upgrade() -> None:
    op.add_column("backings", sa.Column("claim_code", sa.String(length=16), nullable=True), schema="app")
    op.add_column("backings", sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True), schema="app")
    op.add_column("backings", sa.Column("claimed_by", sa.String(length=255), nullable=True), schema="app")
    conn = op.get_bind()
    ids = conn.execute(sa.text("SELECT id FROM app.backings")).scalars().all()
    for backing_id in ids:
        code = "".join(secrets.choice(ALPHABET) for _ in range(12))
        conn.execute(sa.text("UPDATE app.backings SET claim_code = :c WHERE id = :i"),
                     {"c": code, "i": backing_id})
    op.alter_column("backings", "claim_code", nullable=False, schema="app")
    op.create_unique_constraint(op.f("uq_backings_claim_code"), "backings", ["claim_code"], schema="app")


def downgrade() -> None:
    op.drop_constraint(op.f("uq_backings_claim_code"), "backings", schema="app", type_="unique")
    op.drop_column("backings", "claimed_by", schema="app")
    op.drop_column("backings", "claimed_at", schema="app")
    op.drop_column("backings", "claim_code", schema="app")
