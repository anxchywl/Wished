"""add discover order positions"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "202606290001"
down_revision: str | None = "202606270004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.add_column("follows", sa.Column("position", sa.Integer(), nullable=True))
    op.add_column("fulfilled_wishes", sa.Column("position", sa.Integer(), nullable=True))

    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY follower_user_id
                    ORDER BY created_at DESC, id DESC
                ) - 1 AS position
            FROM follows
        )
        UPDATE follows
        SET position = ranked.position
        FROM ranked
        WHERE follows.id = ranked.id
        """
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                row_number() OVER (
                    PARTITION BY participant_user_id
                    ORDER BY fulfilled_at DESC, id DESC
                ) - 1 AS position
            FROM fulfilled_wishes
        )
        UPDATE fulfilled_wishes
        SET position = ranked.position
        FROM ranked
        WHERE fulfilled_wishes.id = ranked.id
        """
    )

    op.alter_column("follows", "position", nullable=False)
    op.alter_column("fulfilled_wishes", "position", nullable=False)
    op.create_index(
        "ix_follows_follower_user_id_position", "follows", ["follower_user_id", "position"]
    )
    op.create_index(
        "ix_fulfilled_wishes_participant_user_id_position",
        "fulfilled_wishes",
        ["participant_user_id", "position"],
    )

    op.create_table(
        "booked_wish_orders",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "wish_id",
            UUID(as_uuid=True),
            sa.ForeignKey("wishes.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("user_id", "wish_id", name="uq_booked_wish_orders_user_wish"),
    )
    op.create_index("ix_booked_wish_orders_user_id", "booked_wish_orders", ["user_id"])
    op.create_index("ix_booked_wish_orders_wish_id", "booked_wish_orders", ["wish_id"])
    op.create_index(
        "ix_booked_wish_orders_user_id_position",
        "booked_wish_orders",
        ["user_id", "position"],
    )

    op.execute(
        """
        WITH current_bookings AS (
            SELECT
                r.reserver_user_id AS user_id,
                r.wish_id,
                r.created_at AS ordered_at
            FROM reservations r
            JOIN wishes w ON w.id = r.wish_id
            JOIN wishlists wl ON wl.id = w.wishlist_id
            WHERE r.status = 'active'
              AND wl.owner_user_id != r.reserver_user_id

            UNION

            SELECT
                gg.organizer_user_id AS user_id,
                gg.wish_id,
                gg.created_at AS ordered_at
            FROM group_gifts gg
            JOIN wishes w ON w.id = gg.wish_id
            JOIN wishlists wl ON wl.id = w.wishlist_id
            WHERE gg.status IN ('active', 'completed')
              AND wl.owner_user_id != gg.organizer_user_id

            UNION

            SELECT
                ggc.contributor_user_id AS user_id,
                gg.wish_id,
                ggc.created_at AS ordered_at
            FROM group_gift_contributions ggc
            JOIN group_gifts gg ON gg.id = ggc.group_gift_id
            JOIN wishes w ON w.id = gg.wish_id
            JOIN wishlists wl ON wl.id = w.wishlist_id
            WHERE gg.status IN ('active', 'completed')
              AND ggc.status != 'cancelled'
              AND wl.owner_user_id != ggc.contributor_user_id
        ),
        ranked AS (
            SELECT
                user_id,
                wish_id,
                row_number() OVER (
                    PARTITION BY user_id
                    ORDER BY ordered_at DESC, wish_id DESC
                ) - 1 AS position
            FROM current_bookings
        )
        INSERT INTO booked_wish_orders (user_id, wish_id, position)
        SELECT user_id, wish_id, position
        FROM ranked
        ON CONFLICT (user_id, wish_id) DO NOTHING
        """
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_index("ix_booked_wish_orders_user_id_position", table_name="booked_wish_orders")
    op.drop_index("ix_booked_wish_orders_wish_id", table_name="booked_wish_orders")
    op.drop_index("ix_booked_wish_orders_user_id", table_name="booked_wish_orders")
    op.drop_table("booked_wish_orders")
    op.drop_index("ix_fulfilled_wishes_participant_user_id_position", table_name="fulfilled_wishes")
    op.drop_index("ix_follows_follower_user_id_position", table_name="follows")
    op.drop_column("fulfilled_wishes", "position")
    op.drop_column("follows", "position")
