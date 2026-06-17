"""create reservations"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202606140007"
down_revision: str | None = "202606140005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    op.create_table(
        "reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wish_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("reserver_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["wish_id"], ["wishes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reserver_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('active', 'cancelled')", name="ck_reservations_status"),
    )
    op.create_index(op.f("ix_reservations_wish_id"), "reservations", ["wish_id"], unique=False)
    # partial unique index: only one active reservation per wish
    op.execute(
        "CREATE UNIQUE INDEX uq_reservations_wish_active ON reservations (wish_id) WHERE status = 'active'"
    )


def downgrade() -> None:
    """revert migration"""
    op.execute("DROP INDEX IF EXISTS uq_reservations_wish_active")
    op.drop_index(op.f("ix_reservations_wish_id"), table_name="reservations")
    op.drop_table("reservations")
