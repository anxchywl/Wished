"""add wish image variants and status"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202606190001"
down_revision: str | None = "202606180001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.add_column(
        "wish_images",
        sa.Column("thumbnail_object_name", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "wish_images",
        sa.Column("medium_object_name", sa.String(length=1024), nullable=True),
    )
    op.add_column(
        "wish_images",
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="ready",
        ),
    )
    op.create_check_constraint(
        "ck_wish_images_status",
        "wish_images",
        "status IN ('pending', 'ready', 'failed', 'deleted')",
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_constraint("ck_wish_images_status", "wish_images", type_="check")
    op.drop_column("wish_images", "status")
    op.drop_column("wish_images", "medium_object_name")
    op.drop_column("wish_images", "thumbnail_object_name")
