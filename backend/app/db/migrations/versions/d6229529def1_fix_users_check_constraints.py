"""fix_users_check_constraints"""

from collections.abc import Sequence

from alembic import op


revision: str = "d6229529def1"
down_revision: str | None = "202606190003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.drop_constraint("ck_users_profile_visibility", "users", type_="check")
    op.drop_constraint("ck_users_birthday_visibility", "users", type_="check")
    op.drop_constraint("ck_users_wishlist_visibility", "users", type_="check")

    op.create_check_constraint(
        "ck_users_profile_visibility",
        "users",
        "profile_visibility IN ('private', 'public', 'friends')",
    )
    op.create_check_constraint(
        "ck_users_birthday_visibility",
        "users",
        "birthday_visibility IN ('private', 'public', 'friends', 'hidden')",
    )
    op.create_check_constraint(
        "ck_users_wishlist_visibility",
        "users",
        "wishlist_visibility IN ('private', 'public', 'friends')",
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_constraint("ck_users_wishlist_visibility", "users", type_="check")
    op.drop_constraint("ck_users_birthday_visibility", "users", type_="check")
    op.drop_constraint("ck_users_profile_visibility", "users", type_="check")

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
