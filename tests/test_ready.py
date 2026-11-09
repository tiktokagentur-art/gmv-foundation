"""Readiness reports the database and does not echo credentials."""

from __future__ import annotations

from fastapi.testclient import TestClient

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


def test_ready_ok_against_database(monkeypatch, database_url: str) -> None:
    monkeypatch.setenv("DATABASE_URL", database_url)
    with TestClient(create_app()) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert database_url not in response.text
