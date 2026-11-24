"""Tests for the read-only GitHub App audit (no network, no real key)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import symphony_app_audit as audit  # noqa: E402
import symphony_app_token as sat  # noqa: E402


@pytest.fixture
def key(tmp_path: Path) -> Path:
    path = tmp_path / "test.pem"
    subprocess.run(["openssl", "genrsa", "-out", str(path), "2048"],
                   capture_output=True, check=True)
    path.chmod(0o600)
    return path


def fake_http(calls: list[tuple[str, str]]):
    def http(method, url, headers, body):
        calls.append((method, url))
        if url.endswith("/app"):
            return 200, {"slug": "gmv-symphony-worker", "owner": {"login": "org"},
                         "permissions": {"issues": "read", "metadata": "read"},
                         "events": [], "installations_count": 1,
                         "client_secret": "must-not-leak", "pem": "must-not-leak"}
        if url.endswith("/app/installations"):
            return 200, [{"id": 1, "account": {"login": "org"},
                          "repository_selection": "selected",
                          "permissions": {"issues": "read", "metadata": "read"},
                          "events": [], "suspended_at": None,
                          "access_tokens_url": "https://example.invalid"}]
        if "/apps/" in url:
            assert "Authorization" not in headers
            return 404, None
        raise AssertionError(url)
    return http


def test_audit_reads_only_and_returns_rights(key: Path) -> None:
    calls: list[tuple[str, str]] = []
    result = audit.audit(key, http=fake_http(calls))
    assert all(method == "GET" for method, _ in calls)
    assert [u.rsplit("api.github.com", 1)[1] for _, u in calls] == [
        "/app", "/app/installations", "/apps/gmv-symphony-worker"]
    assert result["app"]["permissions"] == {"issues": "read", "metadata": "read"}
    assert result["installations"][0]["repository_selection"] == "selected"
    assert result["public_apps_slug_http"] == 404
    dumped = json.dumps(result)
    assert "must-not-leak" not in dumped
    assert "access_tokens_url" not in dumped


def test_audit_fails_closed_on_error(key: Path) -> None:
    def http(method, url, headers, body):
        return 401, None
    with pytest.raises(sat.TokenError):
        audit.audit(key, http=http)


def test_jwt_never_in_output(key: Path, capsys, monkeypatch) -> None:
    seen: list[str] = []

    def http(method, url, headers, body):
        seen.append(headers.get("Authorization", ""))
        return fake_http([])(method, url, headers, body)

    monkeypatch.setattr(sat, "urllib_http", http)
    rc = audit.main(["--key", str(key)])
    out = capsys.readouterr()
    assert rc == 0
    jwt = next(s for s in seen if s).split(" ", 1)[1]
    assert jwt not in out.out + out.err
    assert "BEGIN" not in out.out + out.err

