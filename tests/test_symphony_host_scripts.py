"""Static and argument tests for the Symphony host wrapper (no bwrap needed)."""

from __future__ import annotations

import os
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

    def test_only_auth_json_and_pilot_dir_are_rebound(self) -> None:
        binds = self.pairs("--bind")
        self.assertEqual(binds, [str(self.pilot), str(self.home / ".codex" / "auth.json")])
        self.assertLess(self.args.index(str(self.home / ".codex")),
                        self.args.index("--bind", self.args.index(str(self.home / ".codex"))))


class WrapperTests(unittest.TestCase):
    def test_run_symphony_refuses_without_approval(self) -> None:
        env = {k: v for k, v in os.environ.items() if k != "GMV_SYMPHONY_START_APPROVED"}
        with tempfile.TemporaryDirectory() as tmp:
            env["PILOT_DIR"] = tmp
            proc = subprocess.run(["bash", str(HOST / "run-symphony.sh")], env=env,
                                  capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("BLOCKED", proc.stderr)

    def test_wrapper_has_no_guardrail_bypass_flag(self) -> None:
        text = (HOST / "run-symphony.sh").read_text(encoding="utf-8")
        code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
        self.assertNotIn("--i-understand", code)
        self.assertIn("symphony_app_token.py", code)
        self.assertIn('bwrap "${BW[@]}"', code)


if __name__ == "__main__":
    unittest.main()
