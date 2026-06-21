from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ImportClientPayload(BaseModel):
    """product data extracted by the client browser and sent to the backend for validation + image processing"""

    model_config = ConfigDict(extra="forbid")

    original_url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    price: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, max_length=3)
    image_url: str | None = Field(default=None, max_length=2048)
    marketplace: str | None = Field(default=None, max_length=32)

    @field_validator("original_url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()

    @field_validator("currency")
    @classmethod
    def upper_currency(cls, v: str | None) -> str | None:
        return v.upper() if v else None


class ImportResult(BaseModel):
    title: str | None
    description: str | None
    price: Decimal | None
    currency: str | None
    marketplace: str | None
    original_url: str
    pending_image_id: UUID | None
    pending_image_thumbnail_url: str | None
