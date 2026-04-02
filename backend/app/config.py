from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "EvalLedger"
    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    database_url: str = "postgresql+asyncpg://evalledger:evalledger@localhost:5432/evalledger"
    # Leave empty to auto-derive from database_url. Works with both Render
    # (which injects postgres:// URLs) and Fly.io (fly postgres attach).
    sync_database_url: str = ""
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    jwt_secret_key: str = "evalledger-dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    admin_emails: list[str] = Field(default_factory=list)
    storage_backend: Literal["local", "s3"] = "local"
    storage_root: str = "storage"
    storage_bucket: str = "evalledger-artifacts"
    storage_s3_endpoint_url: str | None = None
    storage_s3_access_key_id: str | None = None
    storage_s3_secret_access_key: str | None = None
    storage_s3_region: str = "us-east-1"
    storage_s3_presign_endpoint: str | None = None
    max_public_upload_bytes: int = 10 * 1024 * 1024
    max_authenticated_upload_bytes: int = 250 * 1024 * 1024
    allowed_artifact_extensions: list[str] = Field(default_factory=lambda: [".json", ".jsonl", ".csv", ".parquet"])
    # Set to true only when a Celery worker process is actually deployed.
    # On Render free tier (API-only), this remains false and contamination
    # checks return an "unavailable" status instead of queuing forever.
    worker_enabled: bool = False
    contamination_default_threshold: float = 0.8
    contamination_num_perm: int = 128

    @model_validator(mode="after")
    def _normalise_database_urls(self) -> Settings:
        """Rewrite bare ``postgres://`` / ``postgresql://`` URLs to the
        driver-specific schemes that SQLAlchemy expects.

        Managed Postgres providers (Render, Fly, etc.) return ``postgres://``
        connection strings.  We normalise them here so the rest of the app
        can always assume the correct driver prefix.

        If ``SYNC_DATABASE_URL`` is not set, it is derived automatically from
        ``DATABASE_URL`` by substituting the asyncpg driver for psycopg.
        """
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

        if not self.sync_database_url:
            # Auto-derive sync URL from the now-normalised async URL.
            self.sync_database_url = self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
        elif self.sync_database_url.startswith("postgres://"):
            self.sync_database_url = self.sync_database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif self.sync_database_url.startswith("postgresql://"):
            self.sync_database_url = self.sync_database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
