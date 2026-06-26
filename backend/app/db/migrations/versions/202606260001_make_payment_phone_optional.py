"""make payment phone optional

Revision ID: 202606260001
Revises: 202606250002
Create Date: 2026-06-26 12:41:00.000000

"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa  # noqa: F401


revision: str = "202606260001"
down_revision: str | None = "202606250002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.alter_column("group_gifts", "payment_phone", nullable=True)


def downgrade() -> None:
    """revert migration"""
    op.alter_column("group_gifts", "payment_phone", nullable=False)
