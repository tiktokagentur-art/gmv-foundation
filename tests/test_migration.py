"""The first migration creates schema_meta and can run twice."""

from __future__ import annotations

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text


def test_upgrade_creates_schema_meta(database_url: str) -> None:
    command.upgrade(Config("alembic.ini"), "head")
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            row = connection.execute(text("SELECT version FROM schema_meta")).one()
    finally:
        engine.dispose()
    assert row.version == "1"
