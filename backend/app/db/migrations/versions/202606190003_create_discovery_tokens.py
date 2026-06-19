"""create discovery_tokens table for PostgreSQL-backed ephemeral profile access"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "202606190003"
down_revision: str | None = "202606190002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "discovery_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("token", sa.String(length=64), nullable=False),
        sa.Column("requester_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("target_telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_discovery_tokens_token", "discovery_tokens", ["token"], unique=True)
    op.create_index("ix_discovery_tokens_requester", "discovery_tokens", ["requester_telegram_id"])
    op.create_index("ix_discovery_tokens_target", "discovery_tokens", ["target_telegram_id"])


def downgrade() -> None:
    op.drop_index("ix_discovery_tokens_target", table_name="discovery_tokens")
    op.drop_index("ix_discovery_tokens_requester", table_name="discovery_tokens")
    op.drop_index("ix_discovery_tokens_token", table_name="discovery_tokens")
    op.drop_table("discovery_tokens")
