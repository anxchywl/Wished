from functools import lru_cache

from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """application settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Wished API"
    app_version: str = "0.1.0"
    app_env: str = "development"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"

    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    telegram_mini_app_url: str = ""
    # telegram recommends validating auth_date within minutes, not hours
    telegram_init_data_max_age_seconds: int = 300

    # must be overridden in production — create_app() enforces this at startup
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "wished"
    postgres_user: str = "wished"
    postgres_password: str = "wished"
    database_url: str | None = None

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_url: str | None = None

    minio_endpoint: str = "localhost:9000"
    minio_public_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "wished"
    minio_secret_key: str = "wished-password"
    minio_secure: bool = False
    minio_media_bucket: str = "wished-media"
    minio_presigned_url_expires_seconds: int = 86400

    max_images_per_wish: int = 1
    upload_rate_per_minute: int = 20
    upload_rate_per_hour: int = 100
    upload_rate_per_day: int = 200

    marketplace_import_rate_per_minute: int = 5
    marketplace_import_rate_per_hour: int = 20

    link_preview_rate_per_hour: int = 20
    # optional residential proxy for marketplaces that block datacenter IPs (e.g. Kaspi, Ozon)
    # format: http://user:pass@host:port  — leave empty to disable
    marketplace_proxy_url: str = ""

    # wishlist mutation rate limits
    wishlist_create_per_hour: int = 20
    wishlist_create_per_day: int = 100
    wishlist_edit_per_hour: int = 100
    wishlist_delete_per_hour: int = 20

    # wish mutation rate limits
    wish_create_per_hour: int = 100
    wish_create_per_day: int = 500
    wish_edit_per_hour: int = 300
    wish_delete_per_hour: int = 100

    # follow/unfollow rate limits
    follow_per_hour: int = 100
    unfollow_per_hour: int = 100

    # reservation rate limits
    reservation_create_per_hour: int = 60
    reservation_cancel_per_hour: int = 60

    # notification batching: suppress duplicate category notifications within this window
    notification_batch_window_seconds: int = 60

    # request body size limits
    max_request_body_bytes: int = 2 * 1024 * 1024  # 2 MB
    max_upload_body_bytes: int = 10 * 1024 * 1024  # 10 MB

    allowed_origins: list[str] = Field(default_factory=list)

    # set to True only when the backend is behind a trusted reverse proxy that sets X-Forwarded-For;
    # False by default — use the direct TCP connection IP for rate limiting
    trust_proxy_headers: bool = False

    admin_telegram_ids: list[int] = Field(default_factory=list)

    @field_validator("admin_telegram_ids", mode="before")
    @classmethod
    def parse_admin_telegram_ids(cls, v: object) -> list[int]:
        if isinstance(v, list):
            return [int(x) for x in v]
        if isinstance(v, int):
            return [v]
        if isinstance(v, str):
            val = v.strip()
            if not val:
                return []
            return [int(x.strip()) for x in val.split(",") if x.strip()]
        return []

    @computed_field
    @property
    def sqlalchemy_database_url(self) -> str:
        """build database url"""
        if self.database_url:
            return self._normalize_async_database_url(self.database_url)
        url = (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )
        return self._normalize_async_database_url(url)

    @computed_field
    @property
    def redis_connection_url(self) -> str:
        """build redis url"""
        if self.redis_url:
            return self.redis_url
        auth = f":{self.redis_password}@" if self.redis_password else ""
        return f"redis://{auth}{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @staticmethod
    def _normalize_async_database_url(url: str) -> str:
        """normalize database driver"""
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url


@lru_cache
def get_settings() -> Settings:
    """load application settings"""
    return Settings()
