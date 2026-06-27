from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FulfilledWish(Base):
    """wish fulfillment history for participants"""
    __tablename__ = "fulfilled_wishes"
    __table_args__ = (
        UniqueConstraint("wish_id", "participant_user_id", name="uq_fulfilled_wishes_wish_participant"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    wish_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("wishes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    participant_user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    group_gift_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("group_gifts.id", ondelete="SET NULL"),
        nullable=True,
    )
    organizer_user_id: Mapped[UUID | None] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    contributor_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    user_contribution_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_collected_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    fulfilled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    wish = relationship("Wish")
    participant = relationship("User", foreign_keys=[participant_user_id])
    organizer = relationship("User", foreign_keys=[organizer_user_id])
    group_gift = relationship("GroupGift")
