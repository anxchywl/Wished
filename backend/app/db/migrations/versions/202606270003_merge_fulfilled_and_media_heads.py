"""merge fulfilled wishes and media migration heads"""

from collections.abc import Sequence


revision: str = "202606270003"
down_revision: tuple[str, str] = ("202606230001", "202606270002")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """apply migration"""
    pass


def downgrade() -> None:
    """revert migration"""
    pass
