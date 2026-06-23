from pydantic import BaseModel, Field, field_validator


class LinkPreviewRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()


class LinkPreviewResponse(BaseModel):
    title: str | None
    description: str | None
    image_url: str | None
    price: str | None
    source: str | None
