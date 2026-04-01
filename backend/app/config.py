from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: Literal["development", "test", "production"] = "development"
    app_name: str = "EvalLedger"
    app_url: str = "http://localhost:8000"
    frontend_url: str = "http://localhost:3000"
    database_url: str = (
        "postgresql+asyncpg://evalledger:evalledger@localhost:5432/evalledger"
    )
    sync_database_url: str = "postgresql+psycopg://evalledger:evalledger@localhost:5432/evalledger"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    jwt_secret_key: str = "evalledger-dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    storage_backend: Literal["local", "s3"] = "local"
    storage_root: str = "storage"
    storage_bucket: str = "evalledger-artifacts"
    storage_s3_endpoint_url: str | None = None
    storage_s3_access_key_id: str | None = None
    storage_s3_secret_access_key: str | None = None
    storage_s3_region: str = "us-east-1"
    storage_s3_presign_endpoint: str | None = None
    max_public_upload_bytes: int = 10 * 1024 * 1024
    contamination_default_threshold: float = 0.8
    contamination_num_perm: int = 128


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

