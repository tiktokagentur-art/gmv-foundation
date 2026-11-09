"""Database connectivity and the infrastructure schema marker.

schema_meta is not a domain model. Domain tables belong to a later package.
"""

from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import DateTime, String, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
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


def database_ready(url: str) -> bool:
    try:
        engine = create_engine(
            url,
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
