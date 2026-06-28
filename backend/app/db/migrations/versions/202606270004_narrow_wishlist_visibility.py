"""narrow wishlist_visibility to private/public"""

from collections.abc import Sequence

from alembic import op


revision: str = "202606270004"
down_revision: str | None = "202606270003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.execute(
        "UPDATE users SET wishlist_visibility = 'public' WHERE wishlist_visibility = 'friends'"
    )
    op.drop_constraint("ck_users_wishlist_visibility", "users", type_="check")
    op.create_check_constraint(
        "ck_users_wishlist_visibility",
        "users",
        "wishlist_visibility IN ('private', 'public')",
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_constraint("ck_users_wishlist_visibility", "users", type_="check")
    op.create_check_constraint(
        "ck_users_wishlist_visibility",
        "users",
        "wishlist_visibility IN ('private', 'public', 'friends')",
    )
