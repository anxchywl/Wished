"""image processing pipeline tests"""

import io

import pytest
from PIL import Image


def _make_rgb_image(
    width: int = 400, height: int = 300, color=(100, 149, 237)
) -> bytes:
    """create a minimal in-memory JPEG for testing"""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _make_png_with_alpha(width: int = 200, height: int = 200) -> bytes:
    img = Image.new("RGBA", (width, height), color=(255, 0, 0, 128))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_jpeg_with_exif(width: int = 400, height: int = 300) -> bytes:
    """create JPEG with orientation EXIF tag"""
    img = Image.new("RGB", (width, height), color=(50, 100, 150))
    exif = img.getexif()
    exif[274] = 6  # orientation: 90° CW
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


# ---------------------------------------------------------------------------
# output format
# ---------------------------------------------------------------------------


def test_process_image_returns_two_webp_variants() -> None:
    from app.modules.media.processing import process_image

    content = _make_rgb_image(800, 600)
    thumb, medium = process_image(content)

    for variant in (thumb, medium):
        assert variant[:4] == b"RIFF"
        assert variant[8:12] == b"WEBP"


def test_process_image_accepts_png_with_alpha() -> None:
    from app.modules.media.processing import process_image

    content = _make_png_with_alpha()
    thumb, medium = process_image(content)

    # alpha stripped — output is valid WebP
    assert medium[:4] == b"RIFF"


# ---------------------------------------------------------------------------
# size constraints
# ---------------------------------------------------------------------------


def test_process_image_thumbnail_max_dim() -> None:
    from app.modules.media.processing import THUMBNAIL_MAX_DIM, process_image

    content = _make_rgb_image(1200, 900)
    thumb, _ = process_image(content)

    img = Image.open(io.BytesIO(thumb))
    assert max(img.size) <= THUMBNAIL_MAX_DIM


def test_process_image_medium_max_dim() -> None:
    from app.modules.media.processing import MEDIUM_MAX_DIM, process_image

    content = _make_rgb_image(2400, 1800)
    _, medium = process_image(content)

    img = Image.open(io.BytesIO(medium))
    assert max(img.size) <= MEDIUM_MAX_DIM


def test_process_image_does_not_upscale_small_images() -> None:
    from app.modules.media.processing import process_image

    # 100×80 is smaller than thumbnail max (300)
    content = _make_rgb_image(100, 80)
    thumb, _ = process_image(content)

    img = Image.open(io.BytesIO(thumb))
    assert img.size == (100, 80)


def test_process_image_preserves_aspect_ratio() -> None:
    from app.modules.media.processing import process_image

    content = _make_rgb_image(1200, 400)  # 3:1 ratio
    thumb, _ = process_image(content)

    img = Image.open(io.BytesIO(thumb))
    w, h = img.size
    assert abs(w / h - 3.0) < 0.05


# ---------------------------------------------------------------------------
# metadata stripping
# ---------------------------------------------------------------------------


def test_process_image_strips_exif_metadata() -> None:
    from app.modules.media.processing import process_image

    content = _make_jpeg_with_exif()
    _, medium = process_image(content)

    out = Image.open(io.BytesIO(medium))
    exif = out.getexif()
    # after stripping, no EXIF tags should survive in the WebP output
    assert len(exif) == 0


# ---------------------------------------------------------------------------
# error handling
# ---------------------------------------------------------------------------


def test_process_image_raises_value_error_on_garbage_input() -> None:
    from app.modules.media.processing import process_image

    with pytest.raises(ValueError, match="image could not be processed"):
        process_image(b"not an image at all")


def test_process_image_raises_value_error_on_truncated_jpeg() -> None:
    from app.modules.media.processing import process_image

    with pytest.raises(ValueError):
        process_image(b"\xff\xd8\xff" + b"\x00" * 5)
