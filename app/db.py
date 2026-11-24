"""Database connectivity and the infrastructure schema marker.

schema_meta is not a domain model. Workload credentials live in
``app.credentials``. Domain tables belong to a later package.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from pydantic import SecretStr
from sqlalchemy import DateTime, String, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT_SECONDS = 3


class Base(DeclarativeBase):
    pass


class SchemaMeta(Base):
    """One row per applied foundation schema version."""

    __tablename__ = "schema_meta"

    version: Mapped[str] = mapped_column(String(64), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )


@contextmanager
def open_session(url: SecretStr) -> Iterator[Session]:
    """Open a short-lived session. The URL is read only while connecting.

    Statement parameters are hidden, so a credential hash does not land in an
    engine error string.
    """
    engine = create_engine(
        url.get_secret_value(),
        poolclass=NullPool,
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
    )
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def database_ready(url: SecretStr) -> bool:
    try:
        engine = create_engine(
            url.get_secret_value(),
            poolclass=NullPool,
            pool_pre_ping=True,
            connect_args={"connect_timeout": _CONNECT_TIMEOUT_SECONDS},
        )
    except Exception as exc:
        _log_failure(exc)
        return False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        _log_failure(exc)
        return False
    finally:
        engine.dispose()


def _log_failure(exc: Exception) -> None:
    logger.warning(
        "database readiness check failed",
        extra={"error_type": type(exc).__name__},
    )
