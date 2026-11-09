"""Shared fixtures. Live database tests require DATABASE_URL."""

from __future__ import annotations

import os

import pytest


@pytest.fixture
def database_url() -> str:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        if os.environ.get("CI"):
            pytest.fail("DATABASE_URL is required in CI")
        pytest.skip("DATABASE_URL is not set")
    return url
