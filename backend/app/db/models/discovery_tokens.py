from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DiscoveryToken(Base):
    """temporary profile-access token issued by the Telegram bot"""
    __tablename__ = "discovery_tokens"

    id: Mapped[UUID] = mapped_column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    requester_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    target_telegram_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
