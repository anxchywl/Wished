from functools import lru_cache

from pydantic import Field, computed_field
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
    telegram_init_data_max_age_seconds: int = 86_400

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
    minio_presigned_url_expires_seconds: int = 3600

    max_images_per_wish: int = 5
    upload_rate_per_minute: int = 20
    upload_rate_per_hour: int = 100

    allowed_origins: list[str] = Field(default_factory=list)

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
