"""add order positions"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202606170001"
down_revision: str | None = "202606140007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.add_column("wishlists", sa.Column("position", sa.Integer(), nullable=True))
    op.add_column("wishes", sa.Column("position", sa.Integer(), nullable=True))

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY owner_user_id
                    ORDER BY created_at DESC, id DESC
                ) - 1 AS position
            FROM wishlists
        )
        UPDATE wishlists
        SET position = ranked.position
        FROM ranked
        WHERE wishlists.id = ranked.id
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY wishlist_id
                    ORDER BY created_at DESC, id DESC
                ) - 1 AS position
            FROM wishes
        )
        UPDATE wishes
        SET position = ranked.position
        FROM ranked
        WHERE wishes.id = ranked.id
        """
    )

    op.alter_column("wishlists", "position", nullable=False)
    op.alter_column("wishes", "position", nullable=False)
    op.create_index(
        "ix_wishlists_owner_user_id_position", "wishlists", ["owner_user_id", "position"]
    )
    op.create_index("ix_wishes_wishlist_id_position", "wishes", ["wishlist_id", "position"])


def downgrade() -> None:
    """revert migration"""
    op.drop_index("ix_wishes_wishlist_id_position", table_name="wishes")
    op.drop_index("ix_wishlists_owner_user_id_position", table_name="wishlists")
    op.drop_column("wishes", "position")
    op.drop_column("wishlists", "position")
