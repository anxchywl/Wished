from uuid import uuid4
from pydantic import BaseModel, Field, ConfigDict, field_validator
from uuid import UUID


class WishlistReorderRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    wishlist_ids: list[UUID] = Field(min_length=1)

    @field_validator("wishlist_ids")
    @classmethod
    def reject_duplicate_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Wishlist ids must be unique")
        return value


try:
    WishlistReorderRequest.model_validate({"wishlist_ids": [str(uuid4()), str(uuid4())]})
    print("Valid")
except Exception as e:
    print(e)
