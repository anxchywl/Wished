"""add group gift visibility"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202606250002"
down_revision: str | None = "202606250001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.add_column(
        "users",
        sa.Column("group_gift_visibility", sa.String(length=20), server_default="hide", nullable=False),
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_column("users", "group_gift_visibility")
