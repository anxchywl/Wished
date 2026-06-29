"""add public profile usernames"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "202606300001"
down_revision: str | None = "202606290001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RESERVED_NAMES = (
    "admin",
    "api",
    "settings",
    "login",
    "help",
    "support",
    "about",
    "users",
    "me",
    "wishlists",
    "wishes",
    "auth",
    "static",
    "assets",
)


def upgrade() -> None:
    """apply migration"""
    op.add_column("users", sa.Column("public_username", sa.String(length=32), nullable=True))

    reserved = ", ".join(f"'{name}'" for name in RESERVED_NAMES)
    op.execute(
        f"""
        WITH candidates AS (
            SELECT
                id,
                lower(username) AS candidate,
                row_number() OVER (
                    PARTITION BY lower(username)
                    ORDER BY created_at ASC, id ASC
                ) AS duplicate_rank
            FROM users
            WHERE username IS NOT NULL
              AND lower(username) ~ '^[a-z0-9_]{{3,32}}$'
              AND lower(username) NOT IN ({reserved})
        )
        UPDATE users
        SET public_username = candidates.candidate
        FROM candidates
        WHERE users.id = candidates.id
          AND candidates.duplicate_rank = 1
        """
    )
    op.execute(
        """
        UPDATE users
        SET public_username = 'u_' || left(replace(id::text, '-', ''), 30)
        WHERE public_username IS NULL
        """
    )

    op.alter_column("users", "public_username", nullable=False)
    op.create_check_constraint(
        "ck_users_public_username_format",
        "users",
        "public_username ~ '^[a-z0-9_]{3,32}$'",
    )
    op.create_check_constraint(
        "ck_users_public_username_reserved",
        "users",
        f"public_username NOT IN ({reserved})",
    )
    op.create_index(
        "ix_users_public_username",
        "users",
        ["public_username"],
        unique=True,
    )

    op.create_table(
        "profile_username_aliases",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("username", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "username ~ '^[a-z0-9_]{3,32}$'", name="ck_profile_username_aliases_format"
        ),
        sa.CheckConstraint(
            f"username NOT IN ({reserved})",
            name="ck_profile_username_aliases_reserved",
        ),
    )
    op.create_index("ix_profile_username_aliases_user_id", "profile_username_aliases", ["user_id"])
    op.create_index(
        "ix_profile_username_aliases_username",
        "profile_username_aliases",
        ["username"],
        unique=True,
    )


def downgrade() -> None:
    """revert migration"""
    op.drop_index("ix_profile_username_aliases_username", table_name="profile_username_aliases")
    op.drop_index("ix_profile_username_aliases_user_id", table_name="profile_username_aliases")
    op.drop_table("profile_username_aliases")
    op.drop_index("ix_users_public_username", table_name="users")
    op.drop_constraint("ck_users_public_username_reserved", "users", type_="check")
    op.drop_constraint("ck_users_public_username_format", "users", type_="check")
    op.drop_column("users", "public_username")
