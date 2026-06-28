# media cleanup worker
"""
Removes MinIO objects that have no corresponding wish_images DB row and are
older than a configurable grace period.  Handles full, thumbnail, and medium
variant object names tracked in the wish_images table.

Run standalone:
    python -m app.workers.media_cleanup
    python -m app.workers.media_cleanup --dry-run
    python -m app.workers.media_cleanup --grace-hours 2
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import WishImage
from app.db.session import async_session_factory, dispose_db
from app.integrations.minio.client import get_minio_client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

DEFAULT_GRACE_HOURS = 1


async def _load_known_objects(bucket: str) -> set[str]:
    """load all tracked object names (including variants) from wish_images"""
    async with async_session_factory() as db:
        result = await db.execute(
            select(
                WishImage.object_name,
                WishImage.thumbnail_object_name,
                WishImage.medium_object_name,
            ).where(WishImage.bucket == bucket)
        )
        known: set[str] = set()
        for row in result.all():
            full, thumb, medium = row
            known.add(full)
            if thumb:
                known.add(thumb)
            if medium:
                known.add(medium)
        return known


def _list_bucket_objects(bucket: str) -> list[tuple[str, datetime]]:
    """list objects and their last-modified timestamps"""
    client = get_minio_client()
    try:
        objects = list(client.list_objects(bucket, recursive=True))
    except Exception as exc:
        logger.warning("could not list bucket %s: %s", bucket, exc)
        return []
    return [
        (obj.object_name, obj.last_modified.replace(tzinfo=UTC))
        for obj in objects
        if obj.object_name and obj.last_modified
    ]


async def run_cleanup(grace_hours: int = DEFAULT_GRACE_HOURS, dry_run: bool = False) -> None:
    """remove orphaned media objects older than the grace period"""
    settings = get_settings()
    bucket = settings.minio_media_bucket
    cutoff = datetime.now(UTC) - timedelta(hours=grace_hours)

    logger.info(
        "starting media cleanup (bucket=%s, grace=%dh, dry_run=%s)",
        bucket,
        grace_hours,
        dry_run,
    )

    known = await _load_known_objects(bucket)
    all_objects = _list_bucket_objects(bucket)

    orphans = [
        (name, modified)
        for name, modified in all_objects
        if name not in known and modified < cutoff
    ]

    if not orphans:
        logger.info("no orphaned objects found")
        await dispose_db()
        return

    client = get_minio_client()
    deleted = 0
    for name, modified in orphans:
        if dry_run:
            logger.info("dry-run: would delete %s (modified %s)", name, modified.isoformat())
        else:
            try:
                client.remove_object(bucket, name)
                logger.info("deleted orphaned object %s", name)
                deleted += 1
            except Exception as exc:
                logger.warning("failed to delete %s: %s", name, exc)

    if dry_run:
        logger.info("dry-run complete — %d object(s) would be deleted", len(orphans))
    else:
        logger.info("cleanup complete — %d object(s) deleted", deleted)

    await dispose_db()


def main() -> None:
    """parse args and run cleanup"""
    parser = argparse.ArgumentParser(description="media cleanup worker")
    parser.add_argument("--grace-hours", type=int, default=DEFAULT_GRACE_HOURS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    asyncio.run(run_cleanup(grace_hours=args.grace_hours, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
