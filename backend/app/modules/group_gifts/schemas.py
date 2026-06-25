import re
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class GroupGiftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection_type: Literal["immediate", "commit"]
    payment_method: str = Field(min_length=1, max_length=100)
    payment_phone: str = Field(min_length=7, max_length=30)
    payment_comment: str | None = Field(default=None, max_length=500)

    @field_validator("payment_method", "payment_comment", mode="before")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("payment_phone", mode="before")
    @classmethod
    def strip_and_validate_phone(cls, value: str) -> str:
        if isinstance(value, str):
            value = value.strip()
        if not re.match(r"^\+?[\d\s\-]{7,30}$", value):
            raise ValueError("Invalid phone number format")
        return value


class GroupGiftPaymentDetailsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    payment_method: str = Field(min_length=1, max_length=100)
    payment_phone: str = Field(min_length=7, max_length=30)
    payment_comment: str | None = Field(default=None, max_length=500)

    @field_validator("payment_method", "payment_comment", mode="before")
    @classmethod
    def strip_strings(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("payment_phone", mode="before")
    @classmethod
    def strip_and_validate_phone(cls, value: str) -> str:
        if isinstance(value, str):
            value = value.strip()
        if not re.match(r"^\+?[\d\s\-]{7,30}$", value):
            raise ValueError("Invalid phone number format")
        return value


class ContributionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class TransferConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirmed: bool


class ContributionSummary(BaseModel):
    id: UUID
    amount: Decimal
    status: str
    created_at: datetime


class GroupGiftResponse(BaseModel):
    id: UUID
    wish_id: UUID
    collection_type: str
    status: str
    payment_method: str | None
    payment_phone: str | None
    payment_comment: str | None
    total_amount: Decimal | None
    collected_amount: Decimal
    percent_complete: int
    contributor_count: int
    is_organizer: bool
    is_contributor: bool
    my_contribution: ContributionSummary | None
    organizer_display_name: str | None
    created_at: datetime


class GroupGiftSummary(BaseModel):
    """lightweight group gift summary embedded in WishResponse"""
    id: UUID
    status: str
    collection_type: str
    collected_amount: Decimal
    percent_complete: int
    contributor_count: int
    is_organizer: bool
    is_contributor: bool
