"""create follows"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606180001"
down_revision: str | None = "202606170001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.add_column(
        "users",
        sa.Column(
            "booking_visibility", sa.String(length=32), server_default="hide", nullable=False
        ),
    )
    op.create_check_constraint(
        "ck_users_booking_visibility",
        "users",
        "booking_visibility IN ('hide', 'anonymous', 'names')",
    )
    op.create_table(
        "follows",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("follower_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("followed_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["followed_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["follower_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("follower_user_id", "followed_user_id", name="uq_follows_pair"),
    )
    op.create_index(
        op.f("ix_follows_follower_user_id"), "follows", ["follower_user_id"], unique=False
    )
    op.create_index(
        op.f("ix_follows_followed_user_id"), "follows", ["followed_user_id"], unique=False
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_index(op.f("ix_follows_followed_user_id"), table_name="follows")
    op.drop_index(op.f("ix_follows_follower_user_id"), table_name="follows")
    op.drop_table("follows")
    op.drop_constraint("ck_users_booking_visibility", "users", type_="check")
    op.drop_column("users", "booking_visibility")
