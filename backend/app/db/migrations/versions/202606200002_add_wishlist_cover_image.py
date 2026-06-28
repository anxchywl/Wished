"""add wishlist cover image columns

Revision ID: 202606200002
Revises: 202606200001
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "202606200002"
down_revision = "202606200001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wishlists", sa.Column("cover_image_bucket", sa.String(255), nullable=True))
    op.add_column("wishlists", sa.Column("cover_image_object_name", sa.String(1024), nullable=True))
    op.add_column(
        "wishlists", sa.Column("cover_image_thumbnail_object_name", sa.String(1024), nullable=True)
    )
    op.add_column(
        "wishlists", sa.Column("cover_image_medium_object_name", sa.String(1024), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("wishlists", "cover_image_medium_object_name")
    op.drop_column("wishlists", "cover_image_thumbnail_object_name")
    op.drop_column("wishlists", "cover_image_object_name")
    op.drop_column("wishlists", "cover_image_bucket")
