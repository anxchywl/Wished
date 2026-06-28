from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WishlistVisibility = Literal["private", "public"]


class WishlistCreateRequest(BaseModel):
    """wishlist create request"""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=200_000)
    visibility: WishlistVisibility | None = None

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """normalize title"""
        return value.strip()

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        """normalize description"""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WishlistUpdateRequest(BaseModel):
    """wishlist update request"""

    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=200_000)
    visibility: WishlistVisibility | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "WishlistUpdateRequest":
        """reject null fields"""
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Title cannot be null")
        if "visibility" in self.model_fields_set and self.visibility is None:
            raise ValueError("Visibility cannot be null")
        return self

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        """normalize title"""
        return value.strip() if value is not None else None

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        """normalize description"""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WishlistReorderRequest(BaseModel):
    """wishlist reorder request"""

    model_config = ConfigDict(extra="forbid")

    wishlist_ids: list[UUID] = Field(min_length=1)

    @field_validator("wishlist_ids")
    @classmethod
    def reject_duplicate_ids(cls, value: list[UUID]) -> list[UUID]:
        """reject duplicate ids"""
        if len(value) != len(set(value)):
            raise ValueError("Wishlist ids must be unique")
        return value


class WishlistResponse(BaseModel):
    """wishlist response"""

    id: UUID
    owner_user_id: UUID
    title: str
    description: str | None
    visibility: WishlistVisibility
    position: int
    cover_image_url: str | None = None
    cover_thumbnail_url: str | None = None
    cover_medium_url: str | None = None
    created_at: datetime
    updated_at: datetime


class WishlistListResponse(BaseModel):
    """wishlist list response"""

    items: list[WishlistResponse]
