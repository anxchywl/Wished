"""migrate wish_images to use medium as primary object_name, drop full variant

Revision ID: 202606230001
Revises: 202606220002
Create Date: 2026-06-23
"""

from alembic import op

revision = "202606230001"
down_revision = "202606220002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # point object_name at the medium variant for all existing records that have one
    op.execute("""
        UPDATE wish_images
        SET object_name = medium_object_name
        WHERE medium_object_name IS NOT NULL
          AND object_name != medium_object_name
    """)


def downgrade() -> None:
    # not reversible — full objects may have been deleted from MinIO
    pass
