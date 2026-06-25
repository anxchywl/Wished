import re

from pydantic import BaseModel, Field, field_validator

# strip C0/C1 control chars and null bytes that could corrupt DB text columns or
# cause display issues; keep tab (0x09), LF (0x0a), CR (0x0d) for descriptions
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
# numeric price: digits, single decimal separator, optional leading sign
_PRICE_RE = re.compile(r"^[+-]?[\d][\d\s]*([.,]\d+)?$")
# ISO 4217 currency code
_CURRENCY_RE = re.compile(r"^[A-Z]{3}$")


def _sanitize_text(v: str | None) -> str | None:
    if v is None:
        return None
    cleaned = _CONTROL_CHAR_RE.sub("", str(v)).strip()
    return cleaned or None


class LinkPreviewRequest(BaseModel):
    url: str = Field(min_length=1, max_length=2048)

    @field_validator("url")
    @classmethod
    def strip_url(cls, v: str) -> str:
        return v.strip()


class LinkPreviewResponse(BaseModel):
    title: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    # only absolute http/https URLs; javascript:/data:/file: rejected
    image_url: str | None = Field(default=None, max_length=2048)
    # numeric string only — will be parsed as Decimal on wish creation
    price: str | None = Field(default=None, max_length=32)
    # exactly 3 uppercase letters (ISO 4217)
    currency: str | None = Field(default=None, max_length=3)
    # extractor identifier
    source: str | None = Field(default=None, max_length=32)

    @field_validator("title", "description", "source", mode="before")
    @classmethod
    def sanitize_text_field(cls, v: object) -> str | None:
        return _sanitize_text(str(v) if v is not None else None)

    @field_validator("image_url", mode="before")
    @classmethod
    def validate_image_url(cls, v: object) -> str | None:
        if v is None:
            return None
        url = _CONTROL_CHAR_RE.sub("", str(v)).strip()
        if not url.startswith(("https://", "http://")):
            return None
        return url[:2048] or None

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, v: object) -> str | None:
        if v is None:
            return None
        raw = _CONTROL_CHAR_RE.sub("", str(v)).strip()
        # normalise: remove thousands-separators spaces, keep one decimal dot
        normalised = raw.replace(",", ".").replace(" ", "")
        if not _PRICE_RE.match(raw.replace(" ", "")):
            return None
        # keep the normalised decimal form
        return normalised[:32] or None

    @field_validator("currency", mode="before")
    @classmethod
    def validate_currency(cls, v: object) -> str | None:
        if v is None:
            return None
        code = _CONTROL_CHAR_RE.sub("", str(v)).strip().upper()
        return code if _CURRENCY_RE.match(code) else None


class StoreImageRequest(BaseModel):
    image_url: str = Field(min_length=1, max_length=2048)

    @field_validator("image_url")
    @classmethod
    def validate_image_url(cls, v: str) -> str:
        url = v.strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError("image_url must use http or https scheme")
        return url


class StoreImageResponse(BaseModel):
    pending_image_id: str
    thumbnail_url: str | None
