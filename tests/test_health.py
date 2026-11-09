"""Liveness does not open a database connection."""

from __future__ import annotations

from importlib import reload

from fastapi.testclient import TestClient

import app.config as config
from app.main import create_app


def test_health_ok_without_database(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:not-used@127.0.0.1:1/none",
    )
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_config_does_not_read_dotenv_file(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://user:fromfile@127.0.0.1:5432/db\n",
        encoding="utf-8",
    )
    reload(config)
    assert config.database_url() is None
