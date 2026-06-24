"""Shared pytest configuration.

Integration tests (marked ``@pytest.mark.integration``) exercise the real app
against a live Postgres + Redis. They are skipped automatically unless
``DATABASE_URL`` is set, so the default ``pytest`` run (and any environment
without a database) keeps running only the fast, fully-mocked unit tests.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: Iterable[pytest.Item]) -> None:
    if os.environ.get("DATABASE_URL"):
        return
    skip_integration = pytest.mark.skip(
        reason="integration tests require DATABASE_URL pointing at a reachable Postgres"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
