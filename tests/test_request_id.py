"""X-Request-ID is minted or kept, logged, and kept out of /health and /ready bodies."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.logging_config import REQUEST_ID_PATTERN, configure_logging, request_id_context
from app.main import create_app
from app.request_id import RequestIdMiddleware, incoming_request_id, resolve_request_id

_KEPT = "123e4567-e89b-12d3-a456-426614174000"
_SECRET = "postgresql+psycopg://user:supersecret@db.example:5432/app"
_INVALID_IDS = (
    "not-a-uuid",
    "",
    f"{_KEPT} ",
    f"{{{_KEPT}}}",
    "123e4567e89b12d3a456426614174000",
    f"{_KEPT},{_KEPT}",
    "../secrets",
    f"{_KEPT[:-1]}g",
)


def test_resolve_request_id_keeps_uuid_and_replaces_the_rest() -> None:
    assert resolve_request_id(_KEPT) == _KEPT
    assert resolve_request_id(_KEPT.upper()) == _KEPT.upper()
    trailing_newline = f"{_KEPT}\n"
    replaced = resolve_request_id(trailing_newline)
    assert replaced != trailing_newline
    assert "\n" not in replaced
    assert REQUEST_ID_PATTERN.fullmatch(replaced)
    minted = resolve_request_id(None)
    assert REQUEST_ID_PATTERN.fullmatch(minted)
    assert minted != resolve_request_id(None)


def test_incoming_request_id_requires_exactly_one_header() -> None:
    raw = _KEPT.encode("ascii")
    assert incoming_request_id({"type": "http", "headers": []}) is None
    assert incoming_request_id({"type": "http", "headers": [(b"x-request-id", raw)]}) == _KEPT
    duplicated = {
        "type": "http",
        "headers": [(b"x-request-id", raw), (b"x-request-id", raw)],
    }
    assert incoming_request_id(duplicated) is None


def test_health_mints_request_id_without_changing_body() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    request_id = response.headers["x-request-id"]
    assert response.headers.get_list("x-request-id") == [request_id]
    assert REQUEST_ID_PATTERN.fullmatch(request_id)


def test_valid_request_id_is_kept_on_health() -> None:
    with TestClient(create_app()) as client:
        lower = client.get("/health", headers={"X-Request-ID": _KEPT})
        upper = client.get("/health", headers={"X-Request-ID": _KEPT.upper()})
    assert lower.status_code == 200
    assert lower.json() == {"status": "ok"}
    assert lower.headers.get_list("x-request-id") == [_KEPT]
    assert upper.headers.get_list("x-request-id") == [_KEPT.upper()]


@pytest.mark.parametrize("incoming", _INVALID_IDS)
def test_invalid_request_id_is_replaced_on_health(incoming: str) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health", headers={"X-Request-ID": incoming})
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    request_id = response.headers["x-request-id"]
    assert response.headers.get_list("x-request-id") == [request_id]
    assert request_id != incoming
    assert REQUEST_ID_PATTERN.fullmatch(request_id)


def test_ready_keeps_unavailable_body(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/ready", headers={"X-Request-ID": _KEPT})
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert response.headers.get_list("x-request-id") == [_KEPT]


def test_ready_log_lines_carry_the_request_id(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app()) as client:
        first = client.get("/ready", headers={"X-Request-ID": _KEPT})
        second = client.get("/ready")
    assert first.status_code == 503
    assert first.json() == {"status": "unavailable"}
    assert second.status_code == 503
    assert second.json() == {"status": "unavailable"}
    second_id = second.headers["x-request-id"]
    assert REQUEST_ID_PATTERN.fullmatch(second_id)
    assert second_id != _KEPT
    payloads = _app_logs(capsys)
    assert [item["request_id"] for item in payloads] == [_KEPT, second_id]


def test_invalid_request_id_is_not_logged(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/ready", headers={"X-Request-ID": "not-a-uuid"})
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    safe = response.headers["x-request-id"]
    assert REQUEST_ID_PATTERN.fullmatch(safe)
    payloads = _app_logs(capsys)
    assert [item["request_id"] for item in payloads] == [safe]
    assert all("not-a-uuid" not in json.dumps(item) for item in payloads)


def test_request_logs_keep_id_and_redact_secrets(monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", _SECRET)

    def leaky(_url: object) -> bool:
        logging.getLogger("app.db").warning("connect failed %s", _SECRET)
        logging.getLogger("app.db").warning(
            "still in request",
            extra={"request_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"},
        )
        return False

    monkeypatch.setattr("app.main.database_ready", leaky)
    with TestClient(create_app()) as client:
        response = client.get("/ready", headers={"X-Request-ID": _KEPT})
    assert response.status_code == 503
    assert response.json() == {"status": "unavailable"}
    assert _SECRET not in response.text
    captured = capsys.readouterr()
    assert _SECRET not in captured.out
    assert _SECRET not in captured.err
    assert "supersecret" not in captured.err
    payloads = _app_logs_from(captured.err)
    assert [item["request_id"] for item in payloads] == [_KEPT, _KEPT]
    assert all("supersecret" not in item["message"] for item in payloads)
    assert "[REDACTED]" in payloads[0]["message"]


def test_request_id_does_not_stick_after_the_response(monkeypatch, capsys) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    with TestClient(create_app()) as client:
        response = client.get("/ready", headers={"X-Request-ID": _KEPT})
    logging.getLogger("app.test").info("after request")
    payloads = _app_logs(capsys)
    during = [item for item in payloads if item["message"] != "after request"]
    after = [item for item in payloads if item["message"] == "after request"]
    assert response.headers["x-request-id"] == _KEPT
    assert [item["request_id"] for item in during] == [_KEPT]
    assert len(after) == 1
    assert "request_id" not in after[0]


def test_unhandled_exception_log_has_request_id_and_hides_secrets(monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", _SECRET)

    def boom() -> None:
        raise RuntimeError(f"connect {_SECRET}")

    monkeypatch.setattr("app.main.database_url", boom)
    with TestClient(create_app()) as client:
        response = client.get("/ready", headers={"X-Request-ID": _KEPT})
    assert response.status_code == 500
    assert response.headers.get_list("x-request-id") == [_KEPT]
    assert response.text == "Internal Server Error"
    assert _SECRET not in response.text
    captured = capsys.readouterr()
    assert _SECRET not in captured.out
    assert _SECRET not in captured.err
    assert "supersecret" not in captured.err
    payloads = _app_logs_from(captured.err)
    assert len(payloads) == 1
    assert payloads[0]["message"] == "unhandled exception"
    assert payloads[0]["request_id"] == _KEPT
    assert payloads[0]["error_type"] == "RuntimeError"
    assert payloads[0]["path"] == "/ready"
    assert payloads[0]["method"] == "GET"
    assert _SECRET not in payloads[0]["exception"]
    assert "supersecret" not in payloads[0]["exception"]
    assert _SECRET not in json.dumps(payloads[0])
    assert "supersecret" not in json.dumps(payloads[0])


def test_unhandled_exception_redacts_secret_in_path_and_method(monkeypatch, capsys) -> None:
    monkeypatch.setenv("DATABASE_URL", _SECRET)
    configure_logging()

    async def inner(_scope, _receive, _send):
        raise RuntimeError(f"connect {_SECRET}")

    application = RequestIdMiddleware(inner)
    messages: list[dict[str, object]] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {
        "type": "http",
        "method": f"GET {_SECRET}",
        "path": f"/boom/{_SECRET}",
        "headers": [(b"x-request-id", _KEPT.encode("ascii"))],
    }
    asyncio.run(application(scope, receive, send))
    start = messages[0]
    assert start["type"] == "http.response.start"
    assert start["status"] == 500
    body = b"".join(
        message["body"]
        for message in messages
        if message["type"] == "http.response.body" and isinstance(message.get("body"), bytes)
    )
    assert body == b"Internal Server Error"
    captured = capsys.readouterr()
    assert captured.out == ""
    assert _SECRET not in captured.err
    assert "supersecret" not in captured.err
    payload = json.loads(captured.err)
    assert payload["message"] == "unhandled exception"
    assert payload["request_id"] == _KEPT
    assert payload["error_type"] == "RuntimeError"
    assert payload["path"] == "/boom/[REDACTED]"
    assert payload["method"] == "GET [REDACTED]"
    assert _SECRET not in payload["exception"]
    assert "supersecret" not in payload["exception"]


def test_unknown_path_keeps_framework_body() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/missing", headers={"X-Request-ID": _KEPT})
    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}
    assert response.headers.get_list("x-request-id") == [_KEPT]


def test_downstream_sees_the_id_that_is_returned() -> None:
    async def echo(request):
        response = JSONResponse({"seen": request.headers.get("x-request-id")})
        response.headers["X-Request-ID"] = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
        return response

    application = Starlette(routes=[Route("/echo", echo)])
    application.add_middleware(RequestIdMiddleware)
    with TestClient(application) as client:
        kept = client.get("/echo", headers={"X-Request-ID": _KEPT})
        rejected = client.get("/echo", headers={"X-Request-ID": "not-a-uuid"})
    assert kept.json()["seen"] == _KEPT
    assert kept.headers.get_list("x-request-id") == [_KEPT]
    assert rejected.json()["seen"] == rejected.headers["x-request-id"]
    assert REQUEST_ID_PATTERN.fullmatch(rejected.headers["x-request-id"])
    assert "not-a-uuid" not in rejected.headers["x-request-id"]


def test_newline_header_is_replaced_and_not_logged(capsys) -> None:
    configure_logging()
    seen: list[bytes] = []

    async def inner(scope, _receive, send):
        for name, value in scope["headers"]:
            if name.lower() == b"x-request-id":
                seen.append(value)
        logging.getLogger("app.test").info("during request")
        await send({"type": "http.response.start", "status": 204, "headers": []})
        await send({"type": "http.response.body", "body": b""})

    application = RequestIdMiddleware(inner)
    messages: list[dict[str, object]] = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = {"type": "http", "headers": [(b"x-request-id", b"bad\r\ninjected")]}
    asyncio.run(application(scope, receive, send))
    assert len(seen) == 1
    safe = seen[0].decode("ascii")
    assert REQUEST_ID_PATTERN.fullmatch(safe)
    start = messages[0]
    assert start["type"] == "http.response.start"
    echoed = [value for name, value in start["headers"] if name == b"x-request-id"]
    assert echoed == [safe.encode("ascii")]
    captured = capsys.readouterr()
    assert "injected" not in captured.err
    assert "\r" not in captured.err
    payload = json.loads(captured.err)
    assert payload["message"] == "during request"
    assert payload["request_id"] == safe


def test_formatter_omits_unsafe_request_id(capsys) -> None:
    configure_logging()
    token = request_id_context.set("bad\nline")
    try:
        logging.getLogger("app.test").info("plain")
    finally:
        request_id_context.reset(token)
    captured = capsys.readouterr()
    payload = json.loads(captured.err)
    assert payload["message"] == "plain"
    assert "request_id" not in payload
    assert "bad" not in captured.err


def test_child_logger_receives_request_id(capsys) -> None:
    configure_logging()
    token = request_id_context.set(_KEPT)
    try:
        logging.getLogger("app.db").info("child")
    finally:
        request_id_context.reset(token)
    payload = json.loads(capsys.readouterr().err)
    assert payload["logger"] == "app.db"
    assert payload["request_id"] == _KEPT


def _app_logs(capsys) -> list[dict[str, object]]:
    captured = capsys.readouterr()
    assert captured.out == ""
    return _app_logs_from(captured.err)


def _app_logs_from(stderr: str) -> list[dict[str, object]]:
    payloads = [json.loads(line) for line in stderr.splitlines() if line]
    return [item for item in payloads if str(item["logger"]).startswith("app.")]
