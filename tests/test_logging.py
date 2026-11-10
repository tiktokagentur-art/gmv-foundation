"""Log lines stay JSON and lose credentials."""

from __future__ import annotations

import json
import logging

from app.config import get_settings
from app.logging_config import JsonFormatter, configure_logging, redact


def test_redact_replaces_database_url(monkeypatch) -> None:
    secret = "postgresql+psycopg://user:supersecret@db.example:5432/app"
    monkeypatch.setenv("DATABASE_URL", secret)
    assert secret not in redact(f"failed {secret}")
    assert "[REDACTED]" in redact(f"failed {secret}")


def test_redact_replaces_userinfo_not_loaded_from_env() -> None:
    rendered = redact("boom postgresql+psycopg://alice:wonder@db.example/app")
    assert "wonder" not in rendered
    assert "postgresql+psycopg://[REDACTED]@db.example/app" in rendered


def test_formatter_emits_one_json_object(monkeypatch) -> None:
    secret = "postgresql+psycopg://user:supersecret@db.example:5432/app"
    monkeypatch.setenv("DATABASE_URL", secret)
    record = logging.LogRecord(
        name="app.test",
        level=logging.WARNING,
        pathname=__file__,
        lineno=1,
        msg="failed %s",
        args=(secret,),
        exc_info=None,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "WARNING"
    assert payload["logger"] == "app.test"
    assert secret not in payload["message"]
    assert "\n" not in JsonFormatter().format(record)


def test_settings_log_hides_database_url(monkeypatch, capsys) -> None:
    secret = "postgresql+psycopg://user:supersecret@db.example:5432/app"
    monkeypatch.setenv("DATABASE_URL", secret)
    configure_logging()
    settings = get_settings()
    logging.getLogger("app.config").info(
        "loaded %s %r %s %r",
        settings,
        settings,
        settings.database_url,
        settings.database_url,
    )
    captured = capsys.readouterr()
    assert "loaded" in captured.err
    assert secret not in captured.out
    assert secret not in captured.err
    assert "supersecret" not in captured.out
    assert "supersecret" not in captured.err
