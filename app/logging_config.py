"""JSON logs. Secret-bearing values are redacted before they are written."""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime

_USERINFO = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")
_SENSITIVE_NAME_PARTS = ("URL", "PASSWORD", "SECRET", "TOKEN", "KEY")
_REDACTED = "[REDACTED]"


def configure_logging() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy", "sqlalchemy.engine"):
        named = logging.getLogger(name)
        named.handlers.clear()
        named.propagate = True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        try:
            message = record.getMessage()
        except Exception:
            message = str(record.msg)
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(message),
        }
        error_type = getattr(record, "error_type", None)
        if isinstance(error_type, str) and error_type.isidentifier():
            payload["error_type"] = error_type
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def redact(text: str) -> str:
    redacted = text
    for value in _sensitive_env_values():
        redacted = redacted.replace(value, _REDACTED)
    return _USERINFO.sub(rf"\1{_REDACTED}@", redacted)


def _sensitive_env_values() -> list[str]:
    values: list[str] = []
    for name, value in os.environ.items():
        if not value:
            continue
        upper = name.upper()
        if not any(part in upper for part in _SENSITIVE_NAME_PARTS):
            continue
        if "://" in value or "@" in value or len(value) >= 16:
            values.append(value)
    values.sort(key=len, reverse=True)
    return values
