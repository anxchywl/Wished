from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Wishlist(Base):
    """wishlist record"""

    __tablename__ = "wishlists"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    owner_user_id: Mapped[UUID] = mapped_column(
        PostgresUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="public")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    cover_image_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    cover_image_object_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    cover_image_thumbnail_object_name: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    cover_image_medium_object_name: Mapped[str | None] = mapped_column(String(1024), nullable=True)
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

    owner = relationship("User", back_populates="wishlists")
    wishes = relationship("Wish", back_populates="wishlist", cascade="all, delete-orphan")
