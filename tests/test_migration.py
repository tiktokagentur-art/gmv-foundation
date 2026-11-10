"""Migrations create schema_meta and, additively, workload credentials."""

from __future__ import annotations

import hashlib

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

_COLUMNS = (
    "created_at",
    "expires_at",
    "id",
    "identity_id",
    "key_hash",
    "kind",
    "prefix",
    "revoked_at",
)


def test_upgrade_creates_schema_meta(database_url: str) -> None:
    command.upgrade(Config("alembic.ini"), "head")
    command.upgrade(Config("alembic.ini"), "head")
    engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            row = connection.execute(text("SELECT version FROM schema_meta")).one()
            count = connection.execute(text("SELECT count(*) FROM schema_meta")).scalar()
    finally:
        engine.dispose()
    assert row.version == "1"
    assert count == 1


def test_credentials_upgrade_is_additive_and_reversible(database_url: str) -> None:
    config = Config("alembic.ini")
    try:
        command.upgrade(config, "head")
        command.downgrade(config, "0001")
        _assert_absent(database_url)
        command.upgrade(config, "head")
        _assert_credentials(database_url)
        command.downgrade(config, "0001")
        _assert_absent(database_url)
    finally:
        command.upgrade(config, "head")


def _assert_absent(database_url: str) -> None:
    engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            present = connection.execute(text("SELECT to_regclass('public.credentials')")).scalar()
            version = connection.execute(text("SELECT version FROM schema_meta")).one()
    finally:
        engine.dispose()
    assert present is None
    assert version.version == "1"


def _assert_credentials(database_url: str) -> None:
    engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            rows = connection.execute(
                text(
                    "SELECT column_name, is_nullable "
                    "FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = 'credentials' "
                    "ORDER BY column_name"
                )
            ).all()
            version = connection.execute(text("SELECT version FROM schema_meta")).one()
            count = connection.execute(text("SELECT count(*) FROM schema_meta")).scalar()
        assert [row.column_name for row in rows] == list(_COLUMNS)
        nullable = {row.column_name: row.is_nullable for row in rows}
        assert nullable["key_hash"] == "NO"
        assert nullable["expires_at"] == "YES"
        assert nullable["revoked_at"] == "YES"
        assert {"key", "secret", "token", "password", "plaintext"}.isdisjoint(nullable)
        assert version.version == "1"
        assert count == 1
        _reject_plaintext(engine)
    finally:
        engine.dispose()


def _reject_plaintext(engine: Engine) -> None:
    digest = hashlib.sha256(b"migration-probe").hexdigest()
    statements = (
        (
            "INSERT INTO credentials (id, identity_id, kind, key_hash, prefix) "
            "VALUES (gen_random_uuid(), gen_random_uuid(), 'service', 'not-a-hash', 'gmv_wk_')"
        ),
        (
            "INSERT INTO credentials (id, identity_id, kind, key_hash, prefix) "
            "VALUES (gen_random_uuid(), gen_random_uuid(), 'human', :digest, 'gmv_wk_')"
        ),
        (
            "INSERT INTO credentials (id, identity_id, kind, key_hash, prefix) "
            "VALUES (gen_random_uuid(), gen_random_uuid(), 'service', :digest, 'other')"
        ),
    )
    for statement in statements:
        with pytest.raises(IntegrityError):
            with engine.begin() as connection:
                connection.execute(text(statement), {"digest": digest})
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO credentials (id, identity_id, kind, key_hash, prefix) "
                "VALUES (gen_random_uuid(), gen_random_uuid(), 'worker', :digest, 'gmv_wk_')"
            ),
            {"digest": digest},
        )
        stored = connection.execute(
            text("SELECT key_hash, prefix, kind FROM credentials WHERE key_hash = :digest"),
            {"digest": digest},
        ).one()
        connection.execute(
            text("DELETE FROM credentials WHERE key_hash = :digest"),
            {"digest": digest},
        )
    assert stored.key_hash == digest
    assert stored.prefix == "gmv_wk_"
    assert stored.kind == "worker"
    assert "migration-probe" not in stored.key_hash
