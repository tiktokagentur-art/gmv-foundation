"""Alembic environment.

DATABASE_URL is read from the process environment. It is not logged.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine, pool

from app.config import database_url
from app.db import Base

config = context.config
url = database_url()
if not url:
    raise RuntimeError("DATABASE_URL is not set")

# ConfigParser treats % as interpolation. Keep the raw URL for the engine.
config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(
        url,
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
