from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.modules.media.schemas import WishImageResponse


class WishCreateRequest(BaseModel):
    """wish create request"""
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    url: str | None = Field(default=None, max_length=2_048)
    priority: int = Field(default=3, ge=1, le=5)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    original_product_url: str | None = Field(default=None, max_length=2_048)
    source_marketplace: str | None = Field(default=None, max_length=32)
    pending_marketplace_image_id: UUID | None = Field(default=None)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        """normalize title"""
        return value.strip()

    @field_validator("description", "url", "original_product_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """normalize optional text"""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("url", "original_product_url")
    @classmethod
    def validate_url_scheme(cls, value: str | None) -> str | None:
        """only allow http and https URLs — blocks javascript:, data:, file:// etc."""
        if value is None:
            return None
        if not value.startswith(("https://", "http://")):
            raise ValueError("URL must use http or https scheme")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        """normalize currency"""
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def validate_price_currency_pair(self) -> "WishCreateRequest":
        """validate price currency"""
        if (self.price is None) != (self.currency is None):
            raise ValueError("Price and currency must be provided together")
        return self


class WishUpdateRequest(BaseModel):
    """wish update request"""
    model_config = ConfigDict(extra="forbid")

    wishlist_id: UUID | None = None
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=2_000)
    url: str | None = Field(default=None, max_length=2_048)
    original_product_url: str | None = Field(default=None, max_length=2_048)
    priority: int | None = Field(default=None, ge=1, le=5)
    price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    currency: str | None = Field(default=None, min_length=3, max_length=3)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        """normalize title"""
        return value.strip() if value is not None else None

    @field_validator("description", "url", "original_product_url")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        """normalize optional text"""
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("url", "original_product_url")
    @classmethod
    def validate_url_scheme(cls, value: str | None) -> str | None:
        """only allow http and https URLs — blocks javascript:, data:, file:// etc."""
        if value is None:
            return None
        if not value.startswith(("https://", "http://")):
            raise ValueError("URL must use http or https scheme")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str | None) -> str | None:
        """normalize currency"""
        return value.upper() if value is not None else None

    @model_validator(mode="after")
    def validate_patch(self) -> "WishUpdateRequest":
        """validate wish patch"""
        if "title" in self.model_fields_set and self.title is None:
            raise ValueError("Title cannot be null")
        if "priority" in self.model_fields_set and self.priority is None:
            raise ValueError("Priority cannot be null")
        if "wishlist_id" in self.model_fields_set and self.wishlist_id is None:
            raise ValueError("Wishlist id cannot be null")
        if ("price" in self.model_fields_set) != ("currency" in self.model_fields_set):
            raise ValueError("Price and currency must be updated together")
        if "price" in self.model_fields_set and (self.price is None) != (self.currency is None):
            raise ValueError("Price and currency must be provided together")
        return self


class WishCopyRequest(BaseModel):
    """wish copy request"""
    model_config = ConfigDict(extra="forbid")

    wishlist_id: UUID


class WishReorderRequest(BaseModel):
    """wish reorder request"""
    model_config = ConfigDict(extra="forbid")

    wish_ids: list[UUID] = Field(min_length=1)

    @field_validator("wish_ids")
    @classmethod
    def reject_duplicate_ids(cls, value: list[UUID]) -> list[UUID]:
        """reject duplicate ids"""
        if len(value) != len(set(value)):
            raise ValueError("Wish ids must be unique")
        return value


class WishResponse(BaseModel):
    """wish response"""
    id: UUID
    wishlist_id: UUID
    title: str
    description: str | None
    url: str | None
    priority: int
    position: int
    price: Decimal | None
    currency: str | None
    status: str
    original_product_url: str | None = None
    source_marketplace: str | None = None
    images: list[WishImageResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class WishListResponse(BaseModel):
    """wish list response"""
    items: list[WishResponse]
