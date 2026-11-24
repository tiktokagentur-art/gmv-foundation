"""HTTP request ids. Unsafe header values are replaced before they reach logs."""

from __future__ import annotations

import hashlib
import logging
import uuid

from starlette.responses import JSONResponse, PlainTextResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.errors import is_v1_path, v1_error_response
from app.logging_config import (
    REQUEST_ID_PATTERN,
    bind_redactions,
    request_id_context,
    reset_redactions,
)

logger = logging.getLogger(__name__)

_HEADER = b"x-request-id"


def resolve_request_id(incoming: str | None) -> str:
    """Keep an incoming UUID. Anything else is replaced with a new one."""
    if incoming is not None and REQUEST_ID_PATTERN.fullmatch(incoming):
        return incoming
    return str(uuid.uuid4())


def incoming_request_id(scope: Scope) -> str | None:
    """Return the sole ``X-Request-ID`` value, or ``None`` when it is absent or repeated."""
    found: list[str] = []
    headers = scope.get("headers") or ()
    for name, value in headers:
        if name.lower() == _HEADER:
            found.append(value.decode("latin-1"))
    if len(found) != 1:
        return None
    return found[0]


class RequestIdMiddleware:
    """Copy or mint ``X-Request-ID`` and put that same value on the response."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = resolve_request_id(incoming_request_id(scope))
        token = request_id_context.set(request_id)
        redaction = bind_redactions(*_authorization_secrets(scope))
        started = False

        async def send_with_request_id(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != _HEADER
                ]
                headers.append((_HEADER, request_id.encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        try:
            await self.app(
                _scope_with_request_id(scope, request_id),
                receive,
                send_with_request_id,
            )
        except Exception as exc:
            # Inside user middleware the request id is still bound. The outer
            # server-error handler runs only after this context is reset, so a
            # response built there would miss the header.
            if started:
                raise
            _log_unhandled(exc, scope)
            response = _server_error(scope, request_id)
            await response(scope, receive, send_with_request_id)
        finally:
            reset_redactions(redaction)
            request_id_context.reset(token)


def _scope_with_request_id(scope: Scope, request_id: str) -> Scope:
    headers = [
        (name, value)
        for name, value in (scope.get("headers") or ())
        if name.lower() != _HEADER
    ]
    headers.append((_HEADER, request_id.encode("ascii")))
    updated = dict(scope)
    updated["headers"] = headers
    return updated


def _server_error(scope: Scope, request_id: str) -> JSONResponse | PlainTextResponse:
    """Unhandled ``/v1`` failures use ErrorBody. Other paths keep the text body."""
    path = scope.get("path")
    if isinstance(path, str) and is_v1_path(path):
        body = v1_error_response(500, request_id)
        if body is not None:
            return body
    return PlainTextResponse("Internal Server Error", status_code=500)


def _authorization_secrets(scope: Scope) -> tuple[str, ...]:
    """Bearer material to redact for the whole request. The header is not logged."""
    found: list[str] = []
    for name, value in scope.get("headers") or ():
        if name.lower() != b"authorization":
            continue
        raw = value.decode("latin-1", errors="replace")
        found.append(raw)
        scheme, separator, token = raw.partition(" ")
        if separator != " " or scheme.lower() != "bearer":
            continue
        token = token.strip()
        if not token:
            continue
        found.append(token)
        found.append(hashlib.sha256(token.encode("utf-8")).hexdigest())
    return tuple(found)


def _log_unhandled(exc: Exception, scope: Scope) -> None:
    """One JSON error line. The HTTP body stays generic and carries no secrets."""
    error_type = type(exc).__name__
    if not error_type.isidentifier():
        error_type = "Exception"
    extra: dict[str, object] = {"error_type": error_type}
    path = scope.get("path")
    method = scope.get("method")
    if isinstance(path, str):
        extra["path"] = path
    if isinstance(method, str):
        extra["method"] = method
    logger.error(
        "unhandled exception",
        extra=extra,
        exc_info=exc,
    )
