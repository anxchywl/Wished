"""server-side image processing pipeline

strips all metadata (EXIF, GPS, ICC, comments), corrects orientation,
converts to WebP, and generates two size variants (thumbnail + medium).
the original bytes are never stored.
"""

from io import BytesIO

from PIL import Image, ImageOps

THUMBNAIL_MAX_DIM = 300
MEDIUM_MAX_DIM = 1200
WEBP_QUALITY = 88


def _resize_if_larger(img: Image.Image, max_dim: int) -> Image.Image:
    """return a proportionally resized copy when either side exceeds max_dim, else unchanged"""
    w, h = img.size
    if w <= max_dim and h <= max_dim:
        return img
    ratio = min(max_dim / w, max_dim / h)
    return img.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)


def _encode_webp(img: Image.Image, quality: int = WEBP_QUALITY) -> bytes:
    buf = BytesIO()
    img.save(buf, format="WEBP", quality=quality, method=6)
    return buf.getvalue()


def process_image(content: bytes) -> tuple[bytes, bytes]:
    """decode, strip metadata, convert to WebP, return (thumbnail, medium)

    raises ValueError on corrupt or unprocessable input
    """
    try:
        with Image.open(BytesIO(content)) as raw:
            img = ImageOps.exif_transpose(raw)
            if img.mode != "RGB":
                img = img.convert("RGB")

            thumbnail = _encode_webp(_resize_if_larger(img, THUMBNAIL_MAX_DIM))
            medium = _encode_webp(_resize_if_larger(img, MEDIUM_MAX_DIM))

    except Exception as exc:
        raise ValueError(f"image could not be processed: {exc}") from exc

    return thumbnail, medium
