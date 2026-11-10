"""Liveness does not open a database connection."""

from __future__ import annotations

from importlib import reload

from fastapi.testclient import TestClient
from pydantic import SecretStr

import app.config as config
from app.main import create_app


def test_health_ok_without_database(monkeypatch) -> None:
    secret = "postgresql+psycopg://user:not-used@127.0.0.1:1/none"
    monkeypatch.setenv("DATABASE_URL", secret)
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert secret not in response.text


def test_config_does_not_read_dotenv_file(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "DATABASE_URL=postgresql+psycopg://user:fromfile@127.0.0.1:5432/db\n",
        encoding="utf-8",
    )
    reload(config)
    assert config.database_url() is None


def test_settings_hide_database_url(monkeypatch) -> None:
    secret = "postgresql+psycopg://user:s3cret-value@127.0.0.1:5432/app"
    monkeypatch.setenv("DATABASE_URL", f"  {secret}  ")
    settings = config.get_settings()
    rendered = "\n".join(
        (
            repr(settings),
            str(settings),
            format(settings),
            repr(settings.database_url),
            str(settings.database_url),
            format(settings.database_url),
            repr(vars(settings)),
        )
    )
    assert isinstance(settings.database_url, SecretStr)
    assert secret not in rendered
    assert "s3cret-value" not in rendered
    loaded = config.database_url()
    assert loaded is not None
    assert loaded.get_secret_value() == secret


def test_blank_database_url_is_unset(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "   ")
    assert config.get_settings().database_url is None
    assert config.database_url() is None


def test_settings_follow_process_environment(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert config.database_url() is None
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:s3cret-value@127.0.0.1:1/none",
    )
    loaded = config.database_url()
    assert loaded is not None
    assert loaded.get_secret_value().endswith("/none")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert config.database_url() is None
