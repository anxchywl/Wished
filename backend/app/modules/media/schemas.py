from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WishImageResponse(BaseModel):
    """wish image response"""
    id: UUID
    wish_id: UUID
    url: str
    thumbnail_url: str | None
    medium_url: str | None
    file_name: str
    content_type: str
    size_bytes: int
    status: str
    created_at: datetime


class WishImageListResponse(BaseModel):
    """wish image list response"""
    items: list[WishImageResponse]
