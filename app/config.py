"""Process configuration.

Values come from the environment only. This module does not read dotenv files.
``DATABASE_URL`` is kept as a pydantic ``SecretStr``. ``str`` and ``repr`` do not
reveal it. Call ``get_secret_value()`` only when opening a connection.
"""

from __future__ import annotations

import os

from pydantic import SecretStr

DATABASE_URL_ENV = "DATABASE_URL"


class Settings:
    """Process settings. The database URL stays masked in ``str`` and ``repr``."""

    def __init__(self, database_url: SecretStr | None) -> None:
        self.database_url = database_url

    def __repr__(self) -> str:
        return f"Settings(database_url={self.database_url!r})"

    def __str__(self) -> str:
        return repr(self)


def get_settings() -> Settings:
    """Read settings from the process environment. No cache and no dotenv file."""
    raw = os.environ.get(DATABASE_URL_ENV)
    if raw is None:
        return Settings(None)
    value = raw.strip()
    if not value:
        return Settings(None)
    return Settings(SecretStr(value))


def database_url() -> SecretStr | None:
    """Return the configured URL, still wrapped, or ``None`` when unset."""
    return get_settings().database_url
