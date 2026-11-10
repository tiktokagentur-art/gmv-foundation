"""Alembic environment.

DATABASE_URL is read from the process environment as a secret.
The plaintext is used only to open the migration connection. It is not logged.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import database_url
from app.db import Base

configured_url = database_url()
if configured_url is None:
    raise RuntimeError("DATABASE_URL is not set")

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=configured_url.get_secret_value(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        configured_url.get_secret_value(),
        poolclass=pool.NullPool,
        connect_args={"connect_timeout": 5},
    )
    try:
        with connectable.connect() as connection:
            context.configure(connection=connection, target_metadata=target_metadata)
            with context.begin_transaction():
                context.run_migrations()
    finally:
        connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
