"""create group gifts"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606250001"
down_revision: str | None = "d6229529def1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.create_table(
        "group_gifts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wish_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organizer_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("collection_type", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("payment_method", sa.String(length=100), nullable=False),
        sa.Column("payment_phone", sa.String(length=30), nullable=False),
        sa.Column("payment_comment", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["wish_id"], ["wishes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organizer_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('active', 'completed', 'cancelled')", name="ck_group_gifts_status"),
        sa.CheckConstraint("collection_type IN ('immediate', 'commit')", name="ck_group_gifts_collection_type"),
    )
    op.create_index(op.f("ix_group_gifts_wish_id"), "group_gifts", ["wish_id"], unique=False)

    op.create_table(
        "group_gift_contributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("group_gift_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("contributor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["group_gift_id"], ["group_gifts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contributor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_group_gift_contributions_group_gift_id"),
        "group_gift_contributions",
        ["group_gift_id"],
        unique=False,
    )

    op.execute("""
        CREATE UNIQUE INDEX uq_group_gifts_wish_active
        ON group_gifts (wish_id)
        WHERE status = 'active'
    """)

    op.execute("""
        CREATE UNIQUE INDEX uq_gg_contrib_active
        ON group_gift_contributions (group_gift_id, contributor_user_id)
        WHERE status NOT IN ('cancelled')
    """)


def downgrade() -> None:
    """revert migration"""
    op.execute("DROP INDEX IF EXISTS uq_gg_contrib_active")
    op.execute("DROP INDEX IF EXISTS uq_group_gifts_wish_active")
    op.drop_index(op.f("ix_group_gift_contributions_group_gift_id"), table_name="group_gift_contributions")
    op.drop_table("group_gift_contributions")
    op.drop_index(op.f("ix_group_gifts_wish_id"), table_name="group_gifts")
    op.drop_table("group_gifts")
