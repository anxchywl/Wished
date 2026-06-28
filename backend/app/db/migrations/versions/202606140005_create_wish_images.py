"""create wish images"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606140005"
down_revision: str | None = "202606140004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.create_table(
        "wish_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wish_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bucket", sa.String(length=255), nullable=False),
        sa.Column("object_name", sa.String(length=1024), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["wish_id"], ["wishes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("object_name"),
        sa.CheckConstraint("size_bytes > 0", name="ck_wish_images_size_positive"),
    )
    op.create_index(op.f("ix_wish_images_wish_id"), "wish_images", ["wish_id"], unique=False)


def downgrade() -> None:
    """revert migration"""
    op.drop_index(op.f("ix_wish_images_wish_id"), table_name="wish_images")
    op.drop_table("wish_images")
