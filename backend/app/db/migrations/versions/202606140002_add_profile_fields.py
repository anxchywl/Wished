"""add profile fields"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "202606140002"
down_revision: str | None = "202606140001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.add_column("users", sa.Column("birthday", sa.Date(), nullable=True))
    op.add_column(
        "users",
        sa.Column("profile_visibility", sa.String(length=32), server_default="public", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("birthday_visibility", sa.String(length=32), server_default="private", nullable=False),
    )
    op.add_column(
        "users",
        sa.Column("wishlist_visibility", sa.String(length=32), server_default="public", nullable=False),
    )
    op.create_check_constraint(
        "ck_users_profile_visibility",
        "users",
        "profile_visibility IN ('private', 'public')",
    )
    op.create_check_constraint(
        "ck_users_birthday_visibility",
        "users",
        "birthday_visibility IN ('private', 'public')",
    )
    op.create_check_constraint(
        "ck_users_wishlist_visibility",
        "users",
        "wishlist_visibility IN ('private', 'public')",
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_constraint("ck_users_wishlist_visibility", "users", type_="check")
    op.drop_constraint("ck_users_birthday_visibility", "users", type_="check")
    op.drop_constraint("ck_users_profile_visibility", "users", type_="check")
    op.drop_column("users", "wishlist_visibility")
    op.drop_column("users", "birthday_visibility")
    op.drop_column("users", "profile_visibility")
    op.drop_column("users", "birthday")
