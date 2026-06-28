"""create wishes"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606140004"
down_revision: str | None = "202606140003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.create_table(
        "wishes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wishlist_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("url", sa.String(length=2048), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["wishlist_id"], ["wishlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("priority >= 1 AND priority <= 5", name="ck_wishes_priority"),
        sa.CheckConstraint("price IS NULL OR price >= 0", name="ck_wishes_price_non_negative"),
        sa.CheckConstraint(
            "(price IS NULL AND currency IS NULL) OR (price IS NOT NULL AND currency IS NOT NULL)",
            name="ck_wishes_price_currency_pair",
        ),
        sa.CheckConstraint(
            "currency IS NULL OR currency = upper(currency)", name="ck_wishes_currency_uppercase"
        ),
    )
    op.create_index(op.f("ix_wishes_wishlist_id"), "wishes", ["wishlist_id"], unique=False)


def downgrade() -> None:
    """revert migration"""
    op.drop_index(op.f("ix_wishes_wishlist_id"), table_name="wishes")
    op.drop_table("wishes")
