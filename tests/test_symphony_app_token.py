"""Tests for the per-run GitHub App token helper. Uses a throwaway key, no network."""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import symphony_app_token as t  # noqa: E402

FAKE_TOKEN = "fake-installation-token-for-tests"
NOW = 1_800_000_000


def b64d(part: str) -> bytes:
    return base64.urlsafe_b64decode(part + "=" * (-len(part) % 4))


def good_response() -> dict:
    return {
        "token": FAKE_TOKEN,
        "expires_at": "2027-01-15T08:00:00Z",
        "permissions": {"issues": "read", "metadata": "read"},
        "repository_selection": "selected",
        "repositories": [{"full_name": t.REPOSITORY}],
    }


class FakeHttp:
    def __init__(self, token_status: int = 201, token_body: dict | None = None) -> None:
        self.calls: list[tuple[str, str, dict, bytes | None]] = []
        self.token_status = token_status
        self.token_body = good_response() if token_body is None else token_body
        self.revoked = False

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        if method == "POST":
            return self.token_status, self.token_body
        if method == "DELETE":
            self.revoked = True
            return 204, None
        if self.revoked:
            return 401, None
        return 200, {"total_count": 1, "repositories": [{"full_name": t.REPOSITORY}]}


class KeyTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls._tmp.name)
        cls.key = cls.dir / "test-only.pem"
        subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048",
             "-out", str(cls.key)],
            check=True, capture_output=True,
        )
        os.chmod(cls.key, 0o600)
        cls.pub = cls.dir / "test-only.pub"
        subprocess.run(["openssl", "pkey", "-in", str(cls.key), "-pubout", "-out", str(cls.pub)],
                       check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()


class JwtTests(KeyTestCase):
    def test_jwt_is_rs256_short_lived_and_verifies(self) -> None:
        jwt = t.build_jwt(t.APP_ID, self.key, now=NOW)
        header_b64, payload_b64, sig_b64 = jwt.split(".")
        self.assertEqual(json.loads(b64d(header_b64)), {"alg": "RS256", "typ": "JWT"})
        payload = json.loads(b64d(payload_b64))
        self.assertEqual(payload["iss"], str(t.APP_ID))
        self.assertLessEqual(payload["exp"] - payload["iat"], 600)
        self.assertLessEqual(payload["exp"] - NOW, 600)
        sig = self.dir / "sig.bin"
        sig.write_bytes(b64d(sig_b64))
        msg = self.dir / "msg.bin"
        msg.write_bytes(f"{header_b64}.{payload_b64}".encode())
        proc = subprocess.run(
            ["openssl", "dgst", "-sha256", "-verify", str(self.pub), "-signature", str(sig),
             str(msg)], capture_output=True, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout)

    def test_ttl_over_ten_minutes_is_rejected(self) -> None:
        for ttl in (0, 541, 600, 3600):
            with self.subTest(ttl=ttl), self.assertRaises(t.TokenError):
                t.build_jwt(t.APP_ID, self.key, now=NOW, ttl=ttl)

    def test_key_permissions_are_enforced(self) -> None:
        loose = self.dir / "loose.pem"
        loose.write_bytes(self.key.read_bytes())
        os.chmod(loose, 0o644)
        with self.assertRaises(t.TokenError):
            t.build_jwt(t.APP_ID, loose, now=NOW)
        with self.assertRaises(t.TokenError):
            t.build_jwt(t.APP_ID, self.dir / "missing.pem", now=NOW)

    def test_errors_do_not_leak_key_material(self) -> None:
        bad = self.dir / "bad.pem"
        bad.write_text("not a key", encoding="utf-8")
        os.chmod(bad, 0o600)
        with self.assertRaises(t.TokenError) as ctx:
            t.build_jwt(t.APP_ID, bad, now=NOW)
        self.assertNotIn("not a key", str(ctx.exception))


class MintTests(KeyTestCase):
    def test_request_is_downscoped(self) -> None:
        http = FakeHttp()
        data = t.mint_installation_token(self.key, http=http, now=NOW)
        self.assertEqual(data["token"], FAKE_TOKEN)
        method, url, headers, body = http.calls[0]
        self.assertEqual(method, "POST")
        self.assertTrue(url.endswith(f"/app/installations/{t.INSTALLATION_ID}/access_tokens"))
        self.assertEqual(json.loads(body), {
            "repositories": ["gmv-foundation"],
            "permissions": {"issues": "read", "metadata": "read"},
        })

    def test_wrong_scope_is_revoked_and_rejected(self) -> None:
        cases = {
            "write": {**good_response(), "permissions": {"issues": "write", "metadata": "read"}},
            "extra": {**good_response(),
                      "permissions": {"issues": "read", "metadata": "read", "contents": "read"}},
            "all repos": {**good_response(), "repository_selection": "all"},
            "other repo": {**good_response(), "repositories": [{"full_name": "x/y"}]},
            "no expiry": {k: v for k, v in good_response().items() if k != "expires_at"},
        }
        for name, body in cases.items():
            http = FakeHttp(token_body=body)
            with self.subTest(name=name), self.assertRaises(t.TokenError):
                t.mint_installation_token(self.key, http=http, now=NOW)
            self.assertTrue(http.revoked, name)

    def test_http_error_fails_closed(self) -> None:
        with self.assertRaises(t.TokenError):
            t.mint_installation_token(self.key, http=FakeHttp(token_status=401, token_body={}),
                                      now=NOW)

    def test_revoke_retries_and_accepts_401(self) -> None:
        statuses = iter([500, 204])
        self.assertTrue(t.revoke("x", lambda *a: (next(statuses), None), sleep=lambda s: None))
        self.assertTrue(t.revoke("x", lambda *a: (401, None), sleep=lambda s: None))
        self.assertFalse(t.revoke("x", lambda *a: (500, None), sleep=lambda s: None))


class ExecTests(KeyTestCase):
    def test_child_gets_only_app_token_and_no_gh_config(self) -> None:
        base = {"PATH": "/usr/bin", "GITHUB_TOKEN": "admin-token", "GH_TOKEN": "admin-token",
                "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "credential.helper",
                "GIT_CONFIG_VALUE_0": "gh"}
        with tempfile.TemporaryDirectory() as tmp:
            env = t.child_env(base, FAKE_TOKEN, Path(tmp))
            self.assertEqual(env["GITHUB_TOKEN"], FAKE_TOKEN)
            self.assertNotIn("admin-token", env.values())
            self.assertNotIn("GH_TOKEN", env)
            self.assertNotIn("GIT_CONFIG_KEY_0", env)
            self.assertEqual(Path(env["GIT_CONFIG_GLOBAL"]).read_text(), "")
            self.assertEqual(list(Path(env["GH_CONFIG_DIR"]).iterdir()), [])

    def test_exec_revokes_after_run_and_never_prints_token(self) -> None:
        http = FakeHttp()
        seen = {}

        def runner(cmd, env):
            seen["token"] = env["GITHUB_TOKEN"]
            return 7

        from contextlib import redirect_stderr, redirect_stdout
        from io import StringIO

        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            rc = t.run_with_token(["true"], self.key, http=http, runner=runner)
        self.assertEqual(rc, 7)
        self.assertEqual(seen["token"], FAKE_TOKEN)
        self.assertTrue(http.revoked)
        self.assertNotIn(FAKE_TOKEN, out.getvalue() + err.getvalue())

    def test_exec_revokes_even_on_crash(self) -> None:
        http = FakeHttp()

        def runner(cmd, env):
            raise RuntimeError("boom")

        with self.assertRaises(RuntimeError):
            t.run_with_token(["true"], self.key, http=http, runner=runner)
        self.assertTrue(http.revoked)

    def test_selftest_output_has_no_token(self) -> None:
        from contextlib import redirect_stdout
        from io import StringIO

        out = StringIO()
        with redirect_stdout(out):
            rc = t.selftest(self.key, http=FakeHttp())
        self.assertEqual(rc, 0)
        self.assertNotIn(FAKE_TOKEN, out.getvalue())
        self.assertIn('"after_revoke_http": 401', out.getvalue())


if __name__ == "__main__":
    unittest.main()
