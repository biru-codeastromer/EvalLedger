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
    # SQLAlchemy async engine connection-pool tuning.
    db_pool_size: int = 10  # Persistent connections kept open per process.
    db_max_overflow: int = 20  # Extra connections allowed past pool_size under load.
    db_pool_timeout: int = 30  # Seconds to wait for a free connection before erroring.
    db_pool_recycle_seconds: int = 1800  # Recycle connections older than this to dodge stale TCP.
    db_pool_pre_ping: bool = True  # Validate connections with a ping before handing them out.
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
    # Public endpoint used when rewriting presigned URLs for external clients.
    # For Cloudflare R2: set to your R2 public bucket domain, e.g.
    # https://pub-<hash>.r2.dev  or your custom domain.
    storage_s3_presign_endpoint: str | None = None
    # Presigned download URL lifetime in seconds (default 1 hour).
    storage_s3_presign_ttl: int = 3600
    max_public_upload_bytes: int = 10 * 1024 * 1024
    max_authenticated_upload_bytes: int = 250 * 1024 * 1024
    allowed_artifact_extensions: list[str] = Field(default_factory=lambda: [".json", ".jsonl", ".csv", ".parquet"])
    # OAuth — GitHub
    # Register an OAuth App at https://github.com/settings/developers
    # Callback URL: {APP_URL}/auth/oauth/github/callback
    github_client_id: str = ""
    github_client_secret: str = ""

    # OAuth — Google
    # Register credentials at https://console.cloud.google.com/apis/credentials
    # Callback URL: {APP_URL}/auth/oauth/google/callback
    google_client_id: str = ""
    google_client_secret: str = ""

    # Logging
    # LOG_LEVEL controls the root log level (DEBUG / INFO / WARNING / ERROR).
    # LOG_HEALTH_REQUESTS=false suppresses /health/live polling from the log stream
    # to avoid noise from Render's 30-second liveness probes.
    log_level: str = "INFO"
    log_health_requests: bool = False

    # Number of trusted reverse proxies in front of the app. Controls how many
    # X-Forwarded-For hops are honoured when deriving the real client IP.
    trusted_proxy_count: int = 1
    # Hard ceiling on request body size in bytes (default 300 MiB) enforced
    # before route handlers run, to bound memory and reject oversized uploads.
    max_request_body_bytes: int = 314572800

    # Rate limiting — set to false to disable globally (e.g. in integration tests).
    # When enabled, a Redis-backed fixed-window limiter is applied to public
    # and write endpoints.  See app/ratelimit.py for bucket definitions.
    rate_limit_enabled: bool = True
    # Per-window download request quotas, split by caller identity.
    download_rate_limit_anon: int = 60  # Requests allowed for anonymous clients.
    download_rate_limit_auth: int = 120  # Requests allowed for authenticated clients.

    # Set to true only when a Celery worker process is actually deployed.
    # On Render free tier (API-only), this remains false and contamination
    # checks return an "unavailable" status instead of queuing forever.
    worker_enabled: bool = False
    contamination_default_threshold: float = 0.8
    contamination_num_perm: int = 128
    # Word n-gram (shingle) size used for MinHash and the exact-Jaccard recheck.
    contamination_shingle_size: int = 5
    # Cap on how many artifact examples a single detection run will process,
    # bounding worst-case memory and runtime for very large uploads.
    contamination_max_examples: int = 100_000
    # Cap on how many flagged examples are persisted/returned per corpus report
    # (the reported count may exceed this; only the stored sample is capped).
    contamination_max_flagged_examples: int = 1_000
    # Truncation length for example/corpus text stored in a flagged record, to
    # bound JSONB row size and avoid echoing large corpus content into the API.
    contamination_max_example_chars: int = 2_000

    @model_validator(mode="after")
    def _validate_s3_settings(self) -> Settings:
        """Raise early if STORAGE_BACKEND=s3 but required credentials are absent.

        All four variables are required:
        - STORAGE_S3_ENDPOINT_URL   — provider endpoint (e.g. Cloudflare R2 URL)
        - STORAGE_S3_ACCESS_KEY_ID  — access key
        - STORAGE_S3_SECRET_ACCESS_KEY — secret key
        - STORAGE_S3_PRESIGN_ENDPOINT  — public domain used in presigned URLs

        This is intentionally a hard error rather than a warning so that a
        misconfigured production deploy fails loudly at startup instead of
        silently falling back to ephemeral local storage.
        """
        if self.storage_backend == "s3":
            missing = [
                name
                for name, value in [
                    ("STORAGE_S3_ENDPOINT_URL", self.storage_s3_endpoint_url),
                    ("STORAGE_S3_ACCESS_KEY_ID", self.storage_s3_access_key_id),
                    ("STORAGE_S3_SECRET_ACCESS_KEY", self.storage_s3_secret_access_key),
                    ("STORAGE_S3_PRESIGN_ENDPOINT", self.storage_s3_presign_endpoint),
                ]
                if not value
            ]
            if missing:
                raise ValueError(
                    f"STORAGE_BACKEND=s3 requires these env vars to be set: "
                    f"{', '.join(missing)}"
                )
        return self

    @model_validator(mode="after")
    def _validate_production_jwt_secret(self) -> Settings:
        """Refuse to boot in production with an insecure JWT signing key.

        ``JWT_SECRET_KEY`` signs the session and OAuth-state tokens, so a
        forgeable key lets anyone mint a token for any user.  If the variable
        is unset, left at the development default, or too short, fail loudly at
        startup (mirroring ``_validate_s3_settings``) instead of silently
        running with a guessable secret.  The development fallback stays usable
        for local and test runs where ``app_env`` is not ``production``.
        """
        if self.app_env == "production":
            insecure_defaults = {"", "evalledger-dev-secret"}
            if self.jwt_secret_key in insecure_defaults or len(self.jwt_secret_key) < 16:
                raise ValueError(
                    "JWT_SECRET_KEY must be set to a strong, unique value "
                    "(at least 16 characters and not the development default) "
                    "when APP_ENV=production."
                )
        return self

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
