"""add wish status column for lifecycle enforcement"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202606190002"
down_revision: str | None = "202606190001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.add_column(
        "wishes",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="active",
        ),
    )
    op.create_check_constraint(
        "ck_wishes_status",
        "wishes",
        "status IN ('active', 'completed', 'archived')",
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_constraint("ck_wishes_status", "wishes", type_="check")
    op.drop_column("wishes", "status")
