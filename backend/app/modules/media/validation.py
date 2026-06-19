"""image upload validation — three-layer check: extension, declared MIME, magic bytes"""

from fastapi import HTTPException, status

ALLOWED_EXTENSIONS: frozenset[str] = frozenset({"jpg", "jpeg", "png", "webp"})
ALLOWED_MIME_TYPES: frozenset[str] = frozenset({"image/jpeg", "image/png", "image/webp"})

_JPEG_MAGIC = b"\xff\xd8\xff"
_PNG_MAGIC = b"\x89\x50\x4e\x47\x0d\x0a\x1a\x0a"
_WEBP_RIFF = b"RIFF"
_WEBP_WEBP = b"WEBP"


def detect_image_mime(content: bytes) -> str | None:
    """return detected MIME type from magic bytes, or None if unrecognised"""
    if content[:3] == _JPEG_MAGIC:
        return "image/jpeg"
    if len(content) >= 8 and content[:8] == _PNG_MAGIC:
        return "image/png"
    if len(content) >= 12 and content[:4] == _WEBP_RIFF and content[8:12] == _WEBP_WEBP:
        return "image/webp"
    return None


def validate_image_upload(filename: str, declared_content_type: str, content: bytes) -> None:
    """three-layer image validation — raises HTTPException on any failure

    layer 1: file extension allowlist
    layer 2: declared Content-Type allowlist (never trusted alone)
    layer 3: magic byte signature verification
    """
    # layer 1: extension
    raw_name = filename or ""
    ext = raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="file extension not allowed",
        )

    # layer 2: declared MIME type
    mime = (declared_content_type or "").lower().split(";")[0].strip()
    if mime not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="content type not allowed",
        )

    # layer 3: magic bytes
    detected = detect_image_mime(content)
    if detected is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="file content does not match a supported image format",
        )

    # magic bytes must agree with the declared MIME (e.g. reject png.jpg)
    # for JPEG variants (image/jpeg covers .jpg and .jpeg) we normalise
    declared_base = mime
    if declared_base == "image/jpeg" and detected == "image/jpeg":
        return
    if declared_base != detected:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="file content does not match declared content type",
        )
