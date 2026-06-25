from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class GroupGift(Base):
    """group gift record — coordinates contributors for a single wish"""
    __tablename__ = "group_gifts"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    wish_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("wishes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    organizer_user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    collection_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="active")
    payment_method: Mapped[str] = mapped_column(String(100), nullable=False)
    payment_phone: Mapped[str] = mapped_column(String(30), nullable=False)
    payment_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    wish = relationship("Wish", back_populates="group_gift")
    organizer = relationship("User", foreign_keys=[organizer_user_id])
    contributions: Mapped[list["GroupGiftContribution"]] = relationship(
        "GroupGiftContribution",
        back_populates="group_gift",
        cascade="all, delete-orphan",
    )


class GroupGiftContribution(Base):
    """individual contribution to a group gift"""
    __tablename__ = "group_gift_contributions"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    group_gift_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("group_gifts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    contributor_user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    group_gift = relationship("GroupGift", back_populates="contributions")
    contributor = relationship("User", foreign_keys=[contributor_user_id])
