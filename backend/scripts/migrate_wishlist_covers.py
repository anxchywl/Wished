"""one-time data migration: extract base64 wishlist covers → MinIO

Safe to re-run: skips wishlists that already have cover_image_object_name set
and skips wishlists whose description contains no embedded [cover:data:...].

Run inside the backend container:
  docker compose exec backend python scripts/migrate_wishlist_covers.py
"""
from __future__ import annotations

import asyncio
import base64
import logging
import re
import sys
from uuid import uuid4

from sqlalchemy import select, text

from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings
from app.integrations.minio import upload_object
from app.modules.media.processing import process_image

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

COVER_RE = re.compile(r"\[cover:(data:[^\]]+)\]")


async def migrate() -> None:
    settings = get_settings()
    bucket = settings.minio_media_bucket
    engine = create_async_engine(settings.sqlalchemy_database_url)

    async with engine.begin() as conn:
        rows = (await conn.execute(
            text(
                "SELECT id, description, cover_image_object_name "
                "FROM wishlists "
                "WHERE description LIKE '%[cover:data:%' "
                "  AND cover_image_object_name IS NULL"
            )
        )).fetchall()

    log.info("found %d wishlists with embedded base64 cover", len(rows))

    migrated = 0
    skipped = 0

    for row in rows:
        wishlist_id, description, existing_obj = row
        if existing_obj:
            skipped += 1
            continue

        match = COVER_RE.search(description or "")
        if not match:
            skipped += 1
            continue

        data_url = match.group(1)
        try:
            _, b64part = data_url.split(",", 1)
            raw_bytes = base64.b64decode(b64part + "==")  # pad to be safe
        except Exception as exc:
            log.warning("wishlist %s: could not decode base64 (%s) — skipping", wishlist_id, exc)
            skipped += 1
            continue

        try:
            thumbnail_bytes, medium_bytes, full_bytes = process_image(raw_bytes)
        except ValueError as exc:
            log.warning("wishlist %s: image processing failed (%s) — skipping", wishlist_id, exc)
            skipped += 1
            continue

        image_id = uuid4()
        full_name = f"wishlists/{wishlist_id}/{image_id}"
        thumb_name = f"wishlists/{wishlist_id}/{image_id}-t"
        medium_name = f"wishlists/{wishlist_id}/{image_id}-m"

        try:
            upload_object(bucket, full_name, full_bytes, "image/webp")
            upload_object(bucket, thumb_name, thumbnail_bytes, "image/webp")
            upload_object(bucket, medium_name, medium_bytes, "image/webp")
        except Exception as exc:
            log.error("wishlist %s: MinIO upload failed (%s) — skipping", wishlist_id, exc)
            skipped += 1
            continue

        clean_description = COVER_RE.sub("", description).strip() or None

        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "UPDATE wishlists SET "
                    "  cover_image_bucket = :bucket, "
                    "  cover_image_object_name = :obj, "
                    "  cover_image_thumbnail_object_name = :thumb, "
                    "  cover_image_medium_object_name = :medium, "
                    "  description = :desc "
                    "WHERE id = :id"
                ),
                {
                    "bucket": bucket,
                    "obj": full_name,
                    "thumb": thumb_name,
                    "medium": medium_name,
                    "desc": clean_description,
                    "id": str(wishlist_id),
                },
            )

        log.info("wishlist %s → migrated (%s)", wishlist_id, full_name)
        migrated += 1

    log.info("done — migrated: %d  skipped: %d", migrated, skipped)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
