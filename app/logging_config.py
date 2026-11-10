"""JSON logs. Secret-bearing values are redacted before they are written.

While a request is active, each line also carries ``request_id``. Uvicorn's
access line uses this same formatter and the same redaction.
"""

from __future__ import annotations

import contextvars
import json
import logging
import os
import re
from datetime import UTC, datetime

_USERINFO = re.compile(r"([a-zA-Z][a-zA-Z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@")
_SENSITIVE_NAME_PARTS = ("URL", "PASSWORD", "SECRET", "TOKEN", "KEY")
_REDACTED = "[REDACTED]"
# ``\Z`` does not match before a trailing newline, unlike ``$``.
REQUEST_ID_PATTERN = re.compile(
    r"\A[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\Z"
)

request_id_context: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id",
    default=None,
)


def configure_logging() -> None:
    """Send process logs, including Uvicorn access lines, through one JSON handler.

    Uvicorn installs its own handlers before the application is imported.
    Clearing those handlers and propagating makes the access line use this
    formatter, so it carries ``request_id`` and the same redaction.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RequestIdFilter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access", "sqlalchemy", "sqlalchemy.engine"):
        named = logging.getLogger(name)
        named.handlers.clear()
        named.propagate = True


class RequestIdFilter(logging.Filter):
    """Attach the active request id to every record that reaches the JSON handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        request_id = request_id_context.get()
        if isinstance(request_id, str) and REQUEST_ID_PATTERN.fullmatch(request_id):
            record.request_id = request_id
        return True


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
        request_id = _request_id(record)
        if request_id is not None:
            payload["request_id"] = request_id
        error_type = getattr(record, "error_type", None)
        if isinstance(error_type, str) and error_type.isidentifier():
            payload["error_type"] = error_type
        for name in ("path", "method"):
            value = getattr(record, name, None)
            if isinstance(value, str):
                payload[name] = redact(value)
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def _request_id(record: logging.LogRecord) -> str | None:
    candidate = getattr(record, "request_id", None)
    if isinstance(candidate, str) and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    candidate = request_id_context.get()
    if isinstance(candidate, str) and REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


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
