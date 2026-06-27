"""create fulfilled wishes"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "202606270002"
down_revision: str | None = "202606270001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.drop_constraint("ck_group_gifts_status", "group_gifts", type_="check")
    op.create_check_constraint(
        "ck_group_gifts_status",
        "group_gifts",
        "status IN ('active', 'completed', 'cancelled', 'archived')",
    )
    op.create_table(
        "fulfilled_wishes",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("wish_id", UUID(as_uuid=True), sa.ForeignKey("wishes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("participant_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("group_gift_id", UUID(as_uuid=True), sa.ForeignKey("group_gifts.id", ondelete="SET NULL"), nullable=True),
        sa.Column("organizer_user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("contributor_count", sa.Integer(), nullable=True),
        sa.Column("user_contribution_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_collected_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("wish_id", "participant_user_id", name="uq_fulfilled_wishes_wish_participant"),
        sa.CheckConstraint("source IN ('booking', 'group_gift')", name="ck_fulfilled_wishes_source"),
    )
    op.create_index(op.f("ix_fulfilled_wishes_wish_id"), "fulfilled_wishes", ["wish_id"], unique=False)
    op.create_index(op.f("ix_fulfilled_wishes_participant_user_id"), "fulfilled_wishes", ["participant_user_id"], unique=False)


def downgrade() -> None:
    """revert migration"""
    op.drop_index(op.f("ix_fulfilled_wishes_participant_user_id"), table_name="fulfilled_wishes")
    op.drop_index(op.f("ix_fulfilled_wishes_wish_id"), table_name="fulfilled_wishes")
    op.drop_table("fulfilled_wishes")
    op.drop_constraint("ck_group_gifts_status", "group_gifts", type_="check")
    op.create_check_constraint(
        "ck_group_gifts_status",
        "group_gifts",
        "status IN ('active', 'completed', 'cancelled')",
    )
