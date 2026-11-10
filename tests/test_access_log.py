"""Uvicorn access lines are JSON, carry the request id, and redact secrets."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

_SECRET = "postgresql+psycopg://user:supersecret@db.example:5432/app"
_KEPT = "123e4567-e89b-12d3-a456-426614174000"
_OTHER = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
_ROOT = Path(__file__).resolve().parents[1]


def test_uvicorn_access_line_contains_the_request_id() -> None:
    port = _free_port()
    env = os.environ.copy()
    env["DATABASE_URL"] = _SECRET
    env["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--no-use-colors",
        ],
        cwd=_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        kept = _exchange(port, "/health", {"X-Request-ID": _KEPT})
        leaked = _exchange(port, f"/health?url={_SECRET}", {"X-Request-ID": _OTHER})
        replaced = _exchange(port, "/health", {"X-Request-ID": "not-a-uuid"})
    except Exception as exc:
        _stdout, stderr = _stop(process)
        raise AssertionError(f"{exc}\n{stderr}") from exc
    stdout, stderr = _stop(process)

    assert kept[0] == 200
    assert json.loads(kept[2]) == {"status": "ok"}
    assert kept[1].get("x-request-id") == _KEPT
    assert leaked[0] == 200
    assert json.loads(leaked[2]) == {"status": "ok"}
    assert leaked[1].get("x-request-id") == _OTHER
    minted = replaced[1].get("x-request-id", "")
    assert replaced[0] == 200
    assert json.loads(replaced[2]) == {"status": "ok"}
    assert minted != "not-a-uuid"
    assert _SECRET not in stdout
    assert _SECRET not in stderr
    assert "supersecret" not in stdout
    assert "supersecret" not in stderr
    assert "not-a-uuid" not in stderr

    access = [item for item in _json_lines(stderr) if item.get("logger") == "uvicorn.access"]
    by_id = {item["request_id"]: item for item in access}
    assert set(by_id) == {_KEPT, _OTHER, minted}
    assert 'GET /health HTTP/1.1" 200' in by_id[_KEPT]["message"]
    assert "[REDACTED]" in by_id[_OTHER]["message"]
    assert _SECRET not in by_id[_OTHER]["message"]
    assert "supersecret" not in by_id[_OTHER]["message"]
    for item in by_id.values():
        assert item["level"] == "INFO"
        assert set(item) == {"timestamp", "level", "logger", "message", "request_id"}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _exchange(port: int, path: str, headers: dict[str, str]) -> tuple[int, dict[str, str], bytes]:
    deadline = time.monotonic() + 15
    last = "no connection"
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1) as client:
                client.settimeout(2)
                lines = [
                    f"GET {path} HTTP/1.1",
                    f"Host: 127.0.0.1:{port}",
                    "Connection: close",
                ]
                lines.extend(f"{name}: {value}" for name, value in headers.items())
                client.sendall(("\r\n".join(lines) + "\r\n\r\n").encode())
                chunks = bytearray()
                while True:
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    chunks.extend(chunk)
            break
        except (ConnectionRefusedError, TimeoutError, OSError) as exc:
            last = str(exc)
            time.sleep(0.05)
    else:
        raise AssertionError(last)
    head, _, body = bytes(chunks).partition(b"\r\n\r\n")
    rows = head.decode("iso-8859-1").split("\r\n")
    status = int(rows[0].split()[1])
    parsed: dict[str, str] = {}
    for row in rows[1:]:
        name, value = row.split(":", 1)
        parsed[name.lower()] = value.strip()
    return status, parsed, body


def _json_lines(text: str) -> list[dict[str, object]]:
    payloads: list[dict[str, object]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("{"):
            continue
        payloads.append(json.loads(stripped))
    return payloads


def _stop(process: subprocess.Popen[str]) -> tuple[str, str]:
    process.terminate()
    try:
        stdout, stderr = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate(timeout=5)
    return stdout or "", stderr or ""
