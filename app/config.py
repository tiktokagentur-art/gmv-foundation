"""Process configuration.

Values come from the environment only. This module does not read dotenv files.
"""

from __future__ import annotations

import os

DATABASE_URL_ENV = "DATABASE_URL"


def database_url() -> str | None:
    raw = os.environ.get(DATABASE_URL_ENV)
    if raw is None:
        return None
    value = raw.strip()
    if not value:
        return None
    return value
