from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, Date, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    """telegram user record"""
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    language_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_premium: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    birthday: Mapped[date | None] = mapped_column(Date, nullable=True)
    profile_visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="friends")
    birthday_visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="friends")
    wishlist_visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="friends")
    booking_visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="hide")
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
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    wishlists = relationship("Wishlist", back_populates="owner", cascade="all, delete-orphan")
