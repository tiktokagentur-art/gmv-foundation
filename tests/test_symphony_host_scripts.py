"""Static and argument tests for the Symphony host wrapper (no bwrap needed)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "scripts" / "symphony_host"


def bwrap_args(home: Path, pilot: Path) -> list[str]:
    env = {**os.environ, "GMV_HOME": str(home), "PILOT_DIR": str(pilot)}
    out = subprocess.run(
        ["bash", "-c", f'source "{HOST}/bwrap-env.sh"; gmv_bwrap_args'],
        env=env, capture_output=True, check=True,
    ).stdout
    return [a.decode() for a in out.split(b"\0") if a]


class BwrapArgsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        base = Path(self._tmp.name)
        self.home = base / "home"
        self.pilot = base / "pilot"
        for d in ("secrets", ".config/gh", ".codex", "cli-config", "sand-data"):
            (self.home / d).mkdir(parents=True)
        (self.home / "agent-data").symlink_to(self.home / "sand-data")
        (self.home / ".gitconfig").write_text("[credential]\n", encoding="utf-8")
        (self.home / ".codex" / "auth.json").write_text("{}", encoding="utf-8")
        self.pilot.mkdir()
        self.args = bwrap_args(self.home, self.pilot)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def pairs(self, flag: str) -> list[str]:
        return [self.args[i + 1] for i, a in enumerate(self.args) if a == flag]

    def test_secret_dirs_are_masked(self) -> None:
        tmpfs = self.pairs("--tmpfs")
        for d in ("secrets", ".config/gh", "cli-config", ".codex"):
            self.assertIn(str(self.home / d), tmpfs)
        self.assertIn("/tmp", tmpfs)
        self.assertIn("/workspace", tmpfs)

    def test_symlinks_are_resolved_once(self) -> None:
        tmpfs = self.pairs("--tmpfs")
        self.assertNotIn(str(self.home / "agent-data"), tmpfs)
        self.assertEqual(tmpfs.count(str((self.home / "sand-data").resolve())), 1)

    def test_git_credentials_masked_with_dev_null(self) -> None:
        i = self.args.index(str(self.home / ".gitconfig"))
        self.assertEqual(self.args[i - 2 : i], ["--ro-bind", "/dev/null"])
        self.assertNotIn(str(self.home / ".git-credentials"), self.args)  # existiert nicht

    def test_only_pilot_dir_is_rebound_writable(self) -> None:
        self.assertEqual(self.pairs("--bind"), [str(self.pilot)])

    def test_auth_json_is_rebound_read_only_after_codex_mask(self) -> None:
        auth = str(self.home / ".codex" / "auth.json")
        self.assertIn(auth, self.pairs("--ro-bind"))
        self.assertNotIn(auth, self.pairs("--bind"))
        self.assertLess(self.args.index(str(self.home / ".codex")), self.args.index(auth))


def _bwrap_usable() -> bool:
    if not shutil.which("bwrap"):
        return False
    probe = subprocess.run(["bwrap", "--dev-bind", "/", "/", "--", "true"],
                           capture_output=True, check=False)
    return probe.returncode == 0


@unittest.skipUnless(_bwrap_usable(), "bwrap with unprivileged user namespaces not available")
class BwrapLiveTests(unittest.TestCase):
    """Runs the real bwrap arguments against a temporary home (no secrets involved)."""

    def test_auth_json_readable_but_not_writable_inside(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home, pilot = Path(tmp) / "home", Path(tmp) / "pilot"
            (home / ".codex").mkdir(parents=True)
            (home / ".codex" / "sessions").mkdir()
            auth = home / ".codex" / "auth.json"
            auth.write_text('{"dummy": true}', encoding="utf-8")
            (home / "secrets").mkdir()
            (home / "secrets" / "key.pem").write_text("dummy", encoding="utf-8")
            pilot.mkdir()
            args = bwrap_args(home, pilot)
            script = (
                f'cat "{auth}" >/dev/null && echo READ_OK; '
                f'(echo x >> "{auth}") 2>/dev/null && echo WRITE_OK || echo WRITE_DENIED; '
                f'(rm -f "{auth}") 2>/dev/null; test -e "{auth}" && echo STILL_THERE; '
                f'test -e "{home}/.codex/sessions" && echo SESSIONS_VISIBLE '
                f'|| echo SESSIONS_HIDDEN; '
                f'test -e "{home}/secrets/key.pem" && echo KEY_VISIBLE || echo KEY_HIDDEN; '
                f'touch "{pilot}/probe" && echo PILOT_WRITE_OK'
            )
            proc = subprocess.run(["bwrap", *args, "--", "bash", "-c", script],
                                  capture_output=True, text=True, check=False)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            out = proc.stdout.split()
            for want in ("READ_OK", "WRITE_DENIED", "STILL_THERE", "SESSIONS_HIDDEN",
                         "KEY_HIDDEN", "PILOT_WRITE_OK"):
                self.assertIn(want, out)
            self.assertEqual(auth.read_text(encoding="utf-8"), '{"dummy": true}')


class WrapperTests(unittest.TestCase):
    def test_run_symphony_refuses_without_approval(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GMV_SYMPHONY_START_APPROVED"}
        with tempfile.TemporaryDirectory() as tmp:
            env["PILOT_DIR"] = tmp
            proc = subprocess.run(["bash", str(HOST / "run-symphony.sh")], env=env,
                                  capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("BLOCKED", proc.stderr)

    @staticmethod
    def _code() -> list[str]:
        text = (HOST / "run-symphony.sh").read_text(encoding="utf-8")
        return [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]

    def test_guardrail_flag_only_behind_per_call_opt_in(self) -> None:
        code = self._code()
        hits = [i for i, ln in enumerate(code) if "--i-understand" in ln]
        self.assertEqual(len(hits), 1)
        guard = code[hits[0] - 1]
        self.assertIn('"${GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED:-}" = "yes"', guard)
        joined = "\n".join(code)
        self.assertIn("unset GMV_SYMPHONY_GUARDRAIL_FLAG_APPROVED GMV_SYMPHONY_START_APPROVED",
                      joined)
        self.assertLess(joined.index("unset GMV_SYMPHONY_GUARDRAIL"), joined.index("exec python3"))

    def test_wrapper_chain_token_watchdog_bwrap(self) -> None:
        joined = "\n".join(self._code())
        tok = joined.index('exec python3 "$TOKEN_PY" exec')
        wd = joined.index('python3 "$WATCHDOG"')
        bw = joined.index('bwrap "${BW[@]}"')
        self.assertLess(tok, wd)
        self.assertLess(wd, bw)
        self.assertIn("--budget 2000000 --reserve 300000", joined)

    def test_run_symphony_refuses_second_run(self) -> None:
        env = {**os.environ, "GMV_SYMPHONY_START_APPROVED": "yes",
               "GMV_SYMPHONY_APP_KEY_PATH": "/nonexistent/key.pem"}
        with tempfile.TemporaryDirectory() as tmp:
            env["PILOT_DIR"] = tmp
            (Path(tmp) / "log").mkdir()
            (Path(tmp) / "log" / "pilot-run.once").write_text("used\n", encoding="utf-8")
            proc = subprocess.run(["bash", str(HOST / "run-symphony.sh")], env=env,
                                  capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("kein zweiter Lauf", proc.stderr)

    def test_watchdog_present_next_to_wrapper(self) -> None:
        self.assertTrue((HOST / "symphony_watchdog.py").is_file())


if __name__ == "__main__":
    unittest.main()
