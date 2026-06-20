"""drop photo_url from users — stored in JWT, not DB

Revision ID: 202606200003
Revises: 202606200002
Create Date: 2026-06-20
"""
from alembic import op

revision = "202606200003"
down_revision = "202606200002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "photo_url")


def downgrade() -> None:
    import sqlalchemy as sa
    op.add_column("users", sa.Column("photo_url", sa.String(2048), nullable=True))
