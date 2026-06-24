"""Tests for Settings validation guards (production JWT secret)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.config import Settings


def test_production_rejects_default_jwt_secret() -> None:
    """Booting in production with the dev-default signing key must fail loudly."""
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(app_env="production", jwt_secret_key="evalledger-dev-secret")


def test_production_rejects_empty_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(app_env="production", jwt_secret_key="")


def test_production_rejects_short_jwt_secret() -> None:
    with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
        Settings(app_env="production", jwt_secret_key="too-short")


def test_production_accepts_strong_jwt_secret() -> None:
    secret = "x" * 40
    settings = Settings(app_env="production", jwt_secret_key=secret)
    assert settings.jwt_secret_key == secret


def test_development_allows_default_jwt_secret() -> None:
    """The development fallback must remain usable for local and test runs."""
    settings = Settings(app_env="development", jwt_secret_key="evalledger-dev-secret")
    assert settings.app_env == "development"
    assert settings.jwt_secret_key == "evalledger-dev-secret"
