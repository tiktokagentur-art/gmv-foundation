"""Workload API keys: issue, revoke, authenticate, and V1 error bodies."""

from __future__ import annotations

import base64
import io
import json
import os
import secrets
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from app.auth import bearer_token
from app.credentials import (
    PREFIX,
    CredentialStoreError,
    IssuedCredential,
    authenticate,
    generate_key,
    hash_key,
    hashes_match,
    issue_credential,
    main,
    revoke_credential,
)
from app.logging_config import REQUEST_ID_PATTERN
from app.main import create_app

ROOT = Path(__file__).resolve().parents[1]
_KEPT = "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def migrated(database_url: str) -> str:
    command.upgrade(Config("alembic.ini"), "head")
    return database_url


def test_generated_key_has_prefix_and_32_bytes() -> None:
    key = generate_key()
    assert key.startswith(PREFIX)
    raw = key.removeprefix(PREFIX)
    decoded = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))
    assert len(decoded) >= 32
    digest = hash_key(key)
    assert digest != key
    assert PREFIX not in digest
    assert len(digest) == 64


def test_issued_repr_hides_the_key() -> None:
    key = generate_key()
    issued = IssuedCredential(
        credential_id=uuid.uuid4(),
        identity_id=uuid.uuid4(),
        kind="worker",
        prefix=PREFIX,
        expires_at=None,
        key=key,
    )
    rendered = "\n".join((repr(issued), str(issued), format(issued)))
    assert key not in rendered
    assert "[REDACTED]" in rendered


def test_hash_compare_rejects_a_different_length_in_constant_time(monkeypatch) -> None:
    calls: list[int] = []
    real = secrets.compare_digest

    def spy(left: bytes, right: bytes) -> bool:
        calls.append(1)
        return real(left, right)

    monkeypatch.setattr("app.credentials.secrets.compare_digest", spy)
    assert hashes_match("abc", "abcd") is False
    assert calls == [1]


def test_malformed_credential_does_not_open_the_store(monkeypatch) -> None:
    calls: list[int] = []
    real = secrets.compare_digest

    def spy(left: bytes, right: bytes) -> bool:
        calls.append(1)
        return real(left, right)

    monkeypatch.setattr("app.credentials.secrets.compare_digest", spy)

    def explode(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("store was opened")

    monkeypatch.setattr("app.credentials.open_session", explode)
    assert authenticate("not-a-workload-credential") is None
    assert authenticate(PREFIX + ("!" * 43)) is None
    assert calls


def test_bearer_parser_accepts_only_one_token() -> None:
    key = generate_key()
    assert bearer_token(None) is None
    assert bearer_token("Basic abc") is None
    assert bearer_token("Bearer") is None
    assert bearer_token(f"Bearer {key}") == key
    assert bearer_token(f"bearer {key}") == key
    assert bearer_token(f"Bearer {key} extra") is None


def test_unknown_key_compares_digest(monkeypatch, migrated: str) -> None:
    calls: list[tuple[bytes, bytes]] = []
    real = secrets.compare_digest

    def spy(left: bytes, right: bytes) -> bool:
        calls.append((left, right))
        return real(left, right)

    monkeypatch.setattr("app.credentials.secrets.compare_digest", spy)
    assert authenticate(generate_key()) is None
    assert calls
    assert all(len(left) == len(right) for left, right in calls)


def test_workers_do_not_share_a_key(migrated: str) -> None:
    left = issue_credential(kind="worker")
    right = issue_credential(kind="worker")
    try:
        assert left.key != right.key
        assert left.identity_id != right.identity_id
        left_subject = authenticate(left.key)
        right_subject = authenticate(right.key)
        assert left_subject is not None
        assert right_subject is not None
        assert left_subject.identity_id == left.identity_id
        assert right_subject.identity_id == right.identity_id
    finally:
        revoke_credential(left.credential_id)
        revoke_credential(right.credential_id)


def test_valid_missing_wrong_revoked_and_expired_keys(migrated: str, capsys) -> None:
    valid = issue_credential(kind="service")
    other = issue_credential(kind="worker")
    expiring = issue_credential(
        kind="worker",
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    expired = issue_credential(
        kind="service",
        expires_at=datetime.now(UTC) - timedelta(hours=1),
    )
    wrong_key = generate_key()
    assert valid.key != other.key
    try:
        with TestClient(create_app()) as client:
            ok = client.get("/v1/whoami", headers=_bearer(valid.key))
            future = client.get("/v1/whoami", headers=_bearer(expiring.key))
            missing = client.get("/v1/whoami", headers={"X-Request-ID": _KEPT})
            wrong = client.get(
                "/v1/whoami",
                headers={**_bearer(wrong_key), "X-Request-ID": _KEPT},
            )
            revoke_credential(valid.credential_id)
            revoked = client.get(
                "/v1/whoami",
                headers={**_bearer(valid.key), "X-Request-ID": _KEPT},
            )
            stale = client.get("/v1/whoami", headers=_bearer(expired.key))
            health = client.get("/health", headers=_bearer(other.key))
            ready = client.get("/ready", headers=_bearer(other.key))
        assert ok.status_code == 200
        assert ok.json() == {"identity_id": str(valid.identity_id), "kind": "service"}
        assert future.status_code == 200
        assert future.json()["kind"] == "worker"
        assert health.status_code == 200
        assert health.json() == {"status": "ok"}
        assert ready.status_code == 200
        assert ready.json() == {"status": "ok"}
        for response in (missing, wrong, revoked):
            _assert_error(response, "unauthorized", _KEPT)
        _assert_error(stale, "unauthorized", stale.headers["x-request-id"])
        captured = capsys.readouterr()
        bodies = ok.text + missing.text + wrong.text + revoked.text + stale.text
        for key in (valid.key, other.key, expiring.key, expired.key, wrong_key):
            _assert_secret_absent(captured.out, key)
            _assert_secret_absent(captured.err, key)
            _assert_secret_absent(bodies, key)
        _assert_row_has_hash_only(migrated, other)
    finally:
        for item in (valid, other, expiring, expired):
            revoke_credential(item.credential_id)


def test_store_outage_under_v1_is_internal_error_body(monkeypatch, migrated: str, capsys) -> None:
    def boom(_url: object) -> None:
        raise CredentialStoreError("credential store failed")

    monkeypatch.setattr("app.credentials.open_session", boom)
    key = generate_key()
    with TestClient(create_app()) as client:
        response = client.get(
            "/v1/whoami",
            headers={**_bearer(key), "X-Request-ID": _KEPT},
        )
    _assert_error(response, "internal", _KEPT)
    captured = capsys.readouterr()
    _assert_secret_absent(captured.out + captured.err + response.text, key)


def test_error_body_for_not_found_forbidden_and_internal(migrated: str, capsys) -> None:
    issued = issue_credential(kind="worker")
    application = create_app()

    @application.get("/v1/forbidden-probe")
    def forbidden_probe() -> None:
        raise HTTPException(status_code=403)

    @application.get("/v1/boom")
    def boom() -> None:
        raise RuntimeError(f"boom {issued.key} {hash_key(issued.key)}")

    try:
        with TestClient(application) as client:
            missing = client.get("/v1/missing", headers={"X-Request-ID": _KEPT})
            forbidden = client.get("/v1/forbidden-probe", headers={"X-Request-ID": _KEPT})
            failed = client.get(
                "/v1/boom",
                headers={**_bearer(issued.key), "X-Request-ID": _KEPT},
            )
            outside = client.get("/missing", headers={"X-Request-ID": _KEPT})
        _assert_error(missing, "not_found", _KEPT)
        _assert_error(forbidden, "forbidden", _KEPT)
        _assert_error(failed, "internal", _KEPT)
        assert outside.status_code == 404
        assert outside.json() == {"detail": "Not Found"}
        captured = capsys.readouterr()
        payloads = [json.loads(line) for line in captured.err.splitlines() if line]
        unhandled = [item for item in payloads if item.get("message") == "unhandled exception"]
        assert len(unhandled) == 1
        assert unhandled[0]["request_id"] == _KEPT
        assert unhandled[0]["error_type"] == "RuntimeError"
        _assert_secret_absent(captured.err, issued.key)
        _assert_secret_absent(failed.text, issued.key)
        assert "[REDACTED]" in captured.err
    finally:
        revoke_credential(issued.credential_id)


def test_cli_prints_the_key_once_and_revoke_removes_it(migrated: str) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = migrated
    env["PYTHONPATH"] = str(ROOT)
    issued = subprocess.run(
        [sys.executable, "-m", "app.credentials", "issue", "--kind", "worker"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
    )
    assert issued.returncode == 0
    fields = _fields(issued.stdout)
    key = fields["key"]
    assert issued.stdout.count(key) == 1
    assert key not in issued.stderr
    assert hash_key(key) not in issued.stdout
    assert hash_key(key) not in issued.stderr
    assert "[REDACTED]" not in issued.stderr
    assert fields["kind"] == "worker"
    assert fields["prefix"] == PREFIX
    who = _whoami(key)
    assert who.status_code == 200
    assert who.json()["identity_id"] == fields["identity_id"]
    revoked = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.credentials",
            "revoke",
            "--credential-id",
            fields["credential_id"],
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
    )
    assert revoked.returncode == 0
    assert key not in revoked.stdout
    assert key not in revoked.stderr
    assert hash_key(key) not in revoked.stdout + revoked.stderr
    again = _whoami(key)
    assert again.status_code == 401
    missing = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.credentials",
            "revoke",
            "--credential-id",
            str(uuid.uuid4()),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=ROOT,
    )
    assert missing.returncode == 1
    assert "Credential nicht gefunden." in missing.stderr
    assert "key=" not in missing.stdout


def test_failed_issue_does_not_print_or_log_the_key(monkeypatch, migrated: str, capsys) -> None:
    seen: list[str] = []
    real = generate_key

    def spy() -> str:
        key = real()
        seen.append(key)
        return key

    class _Session:
        def add(self, _row: object) -> None:
            return None

        def commit(self) -> None:
            raise RuntimeError("disk full")

    @contextmanager
    def boom(_url: object) -> Iterator[_Session]:
        yield _Session()

    monkeypatch.setattr("app.credentials.generate_key", spy)
    monkeypatch.setattr("app.credentials.open_session", boom)
    with pytest.raises(CredentialStoreError):
        issue_credential(kind="service")
    captured = capsys.readouterr()
    assert seen
    _assert_secret_absent(captured.out, seen[0])
    _assert_secret_absent(captured.err, seen[0])
    stream_out = io.StringIO()
    code = main(["issue", "--kind", "service"], out=stream_out)
    assert code == 1
    assert stream_out.getvalue() == ""
    captured = capsys.readouterr()
    for key in seen:
        _assert_secret_absent(captured.out + captured.err + stream_out.getvalue(), key)


def test_openapi_describes_the_workload_api_key() -> None:
    spec = yaml.safe_load((ROOT / "api" / "openapi.yaml").read_text(encoding="utf-8"))
    scheme = spec["components"]["securitySchemes"]["callerCredential"]
    assert scheme["type"] == "http"
    assert scheme["scheme"] == "bearer"
    assert "Platzhalter" not in scheme["description"]
    assert PREFIX in scheme["description"]
    assert "SHA-256" in scheme["description"]
    operation = spec["paths"]["/v1/whoami"]["get"]
    assert operation["operationId"] == "whoami"
    codes = spec["components"]["schemas"]["ErrorCode"]["enum"]
    assert "unauthorized" in codes
    assert "forbidden" in codes
    assert "not_found" in codes
    assert "internal" in codes


def _bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


def _whoami(key: str):
    with TestClient(create_app()) as client:
        return client.get("/v1/whoami", headers=_bearer(key))


def _assert_error(response, code: str, request_id: str) -> None:
    assert response.status_code in {401, 403, 404, 500}
    assert response.headers.get_list("x-request-id") == [request_id]
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "request_id"}
    assert body["error"]["code"] == code
    assert body["error"]["request_id"] == request_id
    assert REQUEST_ID_PATTERN.fullmatch(body["error"]["request_id"])
    assert body["error"]["message"]
    assert "gmv_wk_" not in response.text


def _assert_secret_absent(text: str, key: str) -> None:
    assert key not in text
    assert hash_key(key) not in text


def _assert_row_has_hash_only(database_url: str, issued: IssuedCredential) -> None:
    engine = create_engine(database_url, connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text("SELECT * FROM credentials WHERE id = :id"),
                {"id": issued.credential_id},
            ).mappings().one()
    finally:
        engine.dispose()
    blob = " ".join(str(value) for value in row.values())
    assert issued.key not in blob
    assert row["key_hash"] == hash_key(issued.key)
    assert row["prefix"] == PREFIX
    assert row["kind"] == issued.kind


def _fields(text: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in text.splitlines():
        name, separator, value = line.partition("=")
        assert separator == "="
        fields[name] = value
    return fields
