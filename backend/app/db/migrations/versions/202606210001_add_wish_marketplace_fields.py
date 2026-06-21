"""add original_product_url and source_marketplace to wishes

Revision ID: 202606210001
Revises: 202606200004
Create Date: 2026-06-21
"""
from alembic import op
import sqlalchemy as sa

revision = "202606210001"
down_revision = "202606200004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("wishes", sa.Column("original_product_url", sa.String(2048), nullable=True))
    op.add_column("wishes", sa.Column("source_marketplace", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("wishes", "source_marketplace")
    op.drop_column("wishes", "original_product_url")
