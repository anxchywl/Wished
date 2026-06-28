"""re-add photo_url to users — stores Telegram CDN link, not image bytes

Revision ID: 202606200004
Revises: 202606200003
Create Date: 2026-06-20
"""

from alembic import op
import sqlalchemy as sa

revision = "202606200004"
down_revision = "202606200003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("photo_url", sa.String(2048), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "photo_url")
