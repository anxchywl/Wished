"""add index on wishes.status

Revision ID: 202606220002
Revises: 202606220001
Create Date: 2026-06-22
"""

from alembic import op

revision = "202606220002"
down_revision = "202606220001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_wishes_status", "wishes", ["status"])


def downgrade() -> None:
    op.drop_index("ix_wishes_status", table_name="wishes")
