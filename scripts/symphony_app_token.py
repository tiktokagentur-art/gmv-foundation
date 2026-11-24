#!/usr/bin/env python3
"""Per-run GitHub App installation token for Symphony (ENG-003, issue #74).

Ersetzt das Host-/Admin-Token (persönliches ``gh``-Konto mit ``repo``,
``admin:org``) durch ein kurzlebiges Installation-Token der App
``gmv-symphony-worker``. Ablauf je Lauf:

1. JWT (RS256, ``exp`` <= 10 min) mit dem Private Key signieren. Signiert wird
   per ``openssl``; der Key wird nie in Python geladen, ausgegeben oder kopiert.
2. Installation-Token anfordern, heruntergeskaliert auf ``gmv-foundation`` und
   ``issues: read``, ``metadata: read``. Weicht die Antwort ab: widerrufen, Abbruch.
3. ``exec``: Kindprozess nur mit diesem Token als ``GITHUB_TOKEN`` starten.
   Geerbte Tokens, die ``gh``-Konfiguration und der globale Git-Credential-Helper
   werden für das Kind ausgeblendet. Nach dem Ende wird das Token widerrufen.

Token- und Key-Werte erscheinen nie in Ausgaben, Logs oder Dateien.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

API = "https://api.github.com"
APP_ID = 5899252  # kein Secret
INSTALLATION_ID = 185263574  # kein Secret
REPOSITORY_NAME = "gmv-foundation"
REPOSITORY = f"tiktokagentur-art/{REPOSITORY_NAME}"
DEFAULT_KEY_PATH = Path("/home/box/secrets/gmv-symphony-worker.pem")
EXPECTED_PERMISSIONS = {"issues": "read", "metadata": "read"}
JWT_MAX_TTL = 600
JWT_TTL = 540
JWT_BACKDATE = 60
# Werden im Kindprozess entfernt, damit kein geerbtes (Admin-)Token greift.
STRIPPED_ENV = (
    "GITHUB_TOKEN",
    "GH_TOKEN",
    "GH_ENTERPRISE_TOKEN",
    "GITHUB_ENTERPRISE_TOKEN",
    "GITHUB_PAT",
    "GH_HOST",
)

Http = Callable[[str, str, Mapping[str, str], bytes | None], tuple[int, Any]]


class TokenError(Exception):
    """Fail-closed error. Messages never contain token or key material."""


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def check_key_file(path: Path) -> None:
    try:
        st = path.stat()
    except OSError as exc:
        raise TokenError(f"private key not readable: {path}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise TokenError("private key is not a regular file")
    if st.st_mode & 0o077:
        raise TokenError("private key permissions must be 600 or stricter")
    if st.st_uid != os.getuid():
        raise TokenError("private key must be owned by the running user")


def sign_rs256(message: bytes, key_path: Path) -> bytes:
    proc = subprocess.run(
        ["openssl", "dgst", "-sha256", "-sign", str(key_path)],
        input=message,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        # stderr von openssl wird bewusst nicht weitergereicht.
        raise TokenError("RS256 signing failed")
    return proc.stdout


def build_jwt(app_id: int, key_path: Path, now: float | None = None, ttl: int = JWT_TTL) -> str:
    if not 0 < ttl <= JWT_MAX_TTL - JWT_BACKDATE:
        raise TokenError("JWT lifetime must stay below 10 minutes")
    check_key_file(key_path)
    issued = int(now if now is not None else time.time())
    header = {"alg": "RS256", "typ": "JWT"}
    payload = {"iat": issued - JWT_BACKDATE, "exp": issued + ttl, "iss": str(app_id)}
    signing_input = (
        _b64url(json.dumps(header, separators=(",", ":")).encode())
        + "."
        + _b64url(json.dumps(payload, separators=(",", ":")).encode())
    ).encode("ascii")
    return signing_input.decode("ascii") + "." + _b64url(sign_rs256(signing_input, key_path))


def urllib_http(method: str, url: str, headers: Mapping[str, str], body: bytes | None):
    req = urllib.request.Request(url, data=body, method=method, headers=dict(headers))
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read()
            return resp.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except urllib.error.URLError as exc:
        raise TokenError("GitHub API not reachable") from exc


def _headers(auth: str) -> dict[str, str]:
    return {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {auth}",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "gmv-symphony-worker",
    }


def validate_token_response(status: int, data: Any) -> dict[str, Any]:
    if status != 201 or not isinstance(data, dict):
        raise TokenError(f"installation token request failed (HTTP {status})")
    if not isinstance(data.get("token"), str) or not data["token"]:
        raise TokenError("installation token missing in response")
    if data.get("permissions") != EXPECTED_PERMISSIONS:
        raise TokenError("installation token permissions differ from issues/metadata read")
    repos = data.get("repositories")
    if data.get("repository_selection") != "selected" or not isinstance(repos, list) or [
        r.get("full_name") for r in repos
    ] != [REPOSITORY]:
        raise TokenError("installation token is not limited to gmv-foundation")
    if not isinstance(data.get("expires_at"), str):
        raise TokenError("installation token has no expiry")
    return data


def mint_installation_token(
    key_path: Path,
    app_id: int = APP_ID,
    installation_id: int = INSTALLATION_ID,
    http: Http = urllib_http,
    now: float | None = None,
) -> dict[str, Any]:
    jwt = build_jwt(app_id, key_path, now)
    body = json.dumps(
        {"repositories": [REPOSITORY_NAME], "permissions": EXPECTED_PERMISSIONS}
    ).encode()
    status, data = http(
        "POST", f"{API}/app/installations/{installation_id}/access_tokens", _headers(jwt), body
    )
    try:
        return validate_token_response(status, data)
    except TokenError:
        if isinstance(data, dict) and isinstance(data.get("token"), str):
            revoke(data["token"], http)
        raise


def revoke(
    token: str,
    http: Http = urllib_http,
    attempts: int = 3,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Revoke with retries; a token that is already invalid (401) counts as revoked."""
    for attempt in range(attempts):
        try:
            status, _ = http("DELETE", f"{API}/installation/token", _headers(token), None)
        except TokenError:
            status = 0
        if status in (204, 401):
            return True
        if attempt + 1 < attempts:
            sleep(2.0 * (attempt + 1))
    return False


def child_env(base: Mapping[str, str], token: str, isolated_dir: Path) -> dict[str, str]:
    env = {k: v for k, v in base.items() if k not in STRIPPED_ENV}
    # Keine gh-Konfiguration (hosts.yml mit Admin-Token) und kein globaler
    # Git-Credential-Helper (gh auth git-credential) im Kindprozess.
    gh_dir = isolated_dir / "gh"
    gh_dir.mkdir(mode=0o700, exist_ok=True)
    gitconfig = isolated_dir / "gitconfig"
    gitconfig.write_text("", encoding="utf-8")
    env["GH_CONFIG_DIR"] = str(gh_dir)
    env["GIT_CONFIG_GLOBAL"] = str(gitconfig)
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    for key in [k for k in env if k.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_"))]:
        del env[key]
    env.pop("GIT_CONFIG_COUNT", None)
    env["GITHUB_TOKEN"] = token
    return env


def run_with_token(
    command: Sequence[str],
    key_path: Path,
    http: Http = urllib_http,
    runner: Callable[..., int] | None = None,
) -> int:
    if not command:
        raise TokenError("no command given")
    data = mint_installation_token(key_path, http=http)
    token = data["token"]
    print(f"installation token issued, expires_at={data['expires_at']}", file=sys.stderr)
    try:
        with tempfile.TemporaryDirectory(prefix="gmv-symphony-auth-") as tmp:
            env = child_env(os.environ, token, Path(tmp))
            if runner is None:
                return subprocess.call(list(command), env=env)
            return runner(list(command), env=env)
    finally:
        ok = revoke(token, http)
        print(f"installation token revoked={ok}", file=sys.stderr)


def selftest(key_path: Path, http: Http = urllib_http) -> int:
    data = mint_installation_token(key_path, http=http)
    token = data["token"]
    ok = False
    try:
        status, repos = http(
            "GET", f"{API}/installation/repositories", _headers(token), None
        )
        names = (
            [r.get("full_name") for r in repos.get("repositories", [])]
            if isinstance(repos, dict)
            else []
        )
        ok = status == 200 and names == [REPOSITORY]
        print(
            json.dumps(
                {
                    "token_length": len(token),
                    "expires_at": data["expires_at"],
                    "permissions": data["permissions"],
                    "repositories_http": status,
                    "repositories": names,
                }
            )
        )
    finally:
        revoked = revoke(token, http)
        after, _ = http("GET", f"{API}/installation/repositories", _headers(token), None)
        print(json.dumps({"revoked": revoked, "after_revoke_http": after}))
    return 0 if ok and revoked and after == 401 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--key", type=Path, default=Path(
        os.environ.get("GMV_SYMPHONY_APP_KEY_PATH", str(DEFAULT_KEY_PATH))))
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("selftest")
    ex = sub.add_parser("exec")
    ex.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    try:
        if args.cmd == "selftest":
            return selftest(args.key)
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        return run_with_token(command, args.key)
    except TokenError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
