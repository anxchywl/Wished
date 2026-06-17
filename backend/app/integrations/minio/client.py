from io import BytesIO

from minio import Minio
from minio.commonconfig import CopySource

from app.core.config import get_settings

_client: Minio | None = None


def get_minio_client() -> Minio:
    """load minio client"""
    global _client

    if _client is None:
        settings = get_settings()
        _client = Minio(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )

    return _client


import json


def ensure_bucket(bucket: str) -> None:
    """ensure bucket exists and is public"""
    client = get_minio_client()
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    try:
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket}/*"],
                }
            ],
        }
        client.set_bucket_policy(bucket, json.dumps(policy))
    except Exception:
        pass


def upload_object(
    bucket: str,
    object_name: str,
    content: bytes,
    content_type: str,
) -> None:
    """upload object bytes"""
    ensure_bucket(bucket)
    get_minio_client().put_object(
        bucket_name=bucket,
        object_name=object_name,
        data=BytesIO(content),
        length=len(content),
        content_type=content_type,
    )


def delete_object(bucket: str, object_name: str) -> None:
    """delete object"""
    get_minio_client().remove_object(bucket, object_name)


def copy_object(
    source_bucket: str,
    source_object_name: str,
    target_bucket: str,
    target_object_name: str,
) -> None:
    """copy object"""
    ensure_bucket(target_bucket)
    get_minio_client().copy_object(
        bucket_name=target_bucket,
        object_name=target_object_name,
        source=CopySource(source_bucket, source_object_name),
    )


def get_media_object_url(bucket: str, object_name: str) -> str:
    """build object url"""
    settings = get_settings()
    public_endpoint = settings.minio_public_endpoint.rstrip("/")
    return f"{public_endpoint}/{bucket}/{object_name}"
