"""Readiness reports the database and does not echo credentials."""

from __future__ import annotations

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.db import database_ready
from app.logging_config import REQUEST_ID_PATTERN
from app.main import create_app

_SECRET = "postgresql+psycopg://dbuser:s3cret-value@127.0.0.1:1/none"


def test_ready_503_when_database_url_missing(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}


def test_ready_503_hides_credentials(monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", _SECRET)
    with TestClient(create_app()) as client:
        response = client.get("/ready")
    assert response.status_code == 503
    assert "s3cret-value" not in response.text
    captured = capsys.readouterr()
    assert "s3cret-value" not in captured.out
    assert "s3cret-value" not in captured.err


def test_ready_ok_against_database(monkeypatch, database_url: str, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(create_app()) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert REQUEST_ID_PATTERN.fullmatch(response.headers["x-request-id"])
    assert database_url not in response.text
    assert database_url not in response.headers["x-request-id"]
    captured = capsys.readouterr()
    assert database_url not in captured.out
    assert database_url not in captured.err


def test_database_ready_reads_secret_at_connect(monkeypatch) -> None:
    secret = "postgresql+psycopg://dbuser:s3cret-value@127.0.0.1:1/none"
    seen: list[str] = []

    class _Connection:
        def execute(self, *_args: object, **_kwargs: object) -> None:
            return None

        def __enter__(self) -> _Connection:
            return self

        def __exit__(self, *_args: object) -> bool:
            return False

    class _Engine:
        def connect(self) -> _Connection:
            return _Connection()

        def dispose(self) -> None:
            return None

    def _create_engine(url: str, **_kwargs: object) -> _Engine:
        seen.append(url)
        return _Engine()

    monkeypatch.setattr("app.db.create_engine", _create_engine)
    assert database_ready(SecretStr(secret)) is True
    assert seen == [secret]
