from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Wish(Base):
    """wish record"""
    __tablename__ = "wishes"
    __table_args__ = (
        CheckConstraint("status IN ('active', 'completed', 'archived')", name="ck_wishes_status"),
    )

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    wishlist_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("wishlists.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    original_product_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    source_marketplace: Mapped[str | None] = mapped_column(String(32), nullable=True)
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

    wishlist = relationship("Wishlist", back_populates="wishes")
    images = relationship("WishImage", back_populates="wish", cascade="all, delete-orphan")
    reservation = relationship("Reservation", back_populates="wish", uselist=False, cascade="all, delete-orphan")
    group_gift = relationship("GroupGift", back_populates="wish", uselist=False, lazy="selectin", passive_deletes=True)
