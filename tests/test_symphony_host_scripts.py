"""Static and argument tests for the Symphony host wrapper (no bwrap needed)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST = ROOT / "scripts" / "symphony_host"
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(HOST))

import symphony_watchdog as watchdog  # noqa: E402
from symphony_dispatch_gate import MAX_TOKENS_PER_RUN_CEILING  # noqa: E402


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
    # bwrap-env.sh legt ein tmpfs auf /workspace; ohne dieses Verzeichnis (z. B. auf
    # GitHub-Runnern) kann bwrap den Mountpunkt nicht anlegen. Läuft auf dem Pilot-Host.
    if not shutil.which("bwrap") or not Path("/workspace").is_dir():
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
        self.assertLess(joined.index("unset GMV_SYMPHONY_GUARDRAIL"),
                        joined.index('python3 "$TOKEN_PY" exec'))

    def test_wrapper_chain_token_watchdog_bwrap(self) -> None:
        joined = "\n".join(self._code())
        tok = joined.index('python3 "$TOKEN_PY" exec')
        wd = joined.index('python3 "$WATCHDOG"')
        bw = joined.index('bwrap "${BW[@]}"')
        self.assertLess(tok, wd)
        self.assertLess(wd, bw)
        self.assertIn("--budget 5000000 --reserve 300000", joined)

    def test_budget_matches_gate_ceiling_and_watchdog_default(self) -> None:
        joined = "\n".join(self._code())
        m = re.search(r"--budget (\d+) --reserve (\d+)", joined)
        assert m is not None
        self.assertEqual(int(m.group(1)), MAX_TOKENS_PER_RUN_CEILING)
        self.assertEqual(int(m.group(1)), watchdog.DEFAULT_BUDGET)
        self.assertEqual(int(m.group(2)), watchdog.DEFAULT_RESERVE)
        self.assertEqual(watchdog.DEFAULT_BUDGET, 5_000_000)

    def test_slot_and_once_before_proxy_and_release_on_exit(self) -> None:
        joined = "\n".join(self._code())
        order = [joined.index(x) for x in (
            "quota-check", "trap release_slot EXIT", "slot-acquire", "once-acquire",
            'egress-proxy.sh" start', 'python3 "$TOKEN_PY" exec', "quota-scan")]
        self.assertEqual(order, sorted(order))
        self.assertNotIn("pilot-run.once", joined)
        self.assertIn("exit 9", joined)

    def _run(self, tmp: str, issue: str | None = "42"):
        # Nur Fälle, die vor dem ersten Gate-Aufruf enden (Host-Pfade bleiben unberührt).
        env = {**os.environ, "GMV_SYMPHONY_START_APPROVED": "yes",
               "GMV_SYMPHONY_APP_KEY_PATH": "/nonexistent/key.pem", "PILOT_DIR": tmp}
        env.pop("GMV_SYMPHONY_ISSUE", None)
        if issue is not None:
            env["GMV_SYMPHONY_ISSUE"] = issue
        return subprocess.run(["bash", str(HOST / "run-symphony.sh")], env=env,
                              capture_output=True, text=True, check=False)

    def test_run_symphony_requires_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            for bad in (None, "", "0", "abc", "1;id"):
                with self.subTest(issue=bad):
                    proc = self._run(tmp, bad)
                    self.assertEqual(proc.returncode, 2)
                    self.assertIn("GMV_SYMPHONY_ISSUE", proc.stderr)

    def test_run_symphony_refuses_second_run_per_issue(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            once = Path(tmp) / "log" / "once"
            once.mkdir(parents=True)
            (once / "issue-42.once").write_text("used\n", encoding="utf-8")
            proc = self._run(tmp, "42")
            self.assertEqual(proc.returncode, 2)
            self.assertIn("kein zweiter Lauf", proc.stderr)

    def test_wrapper_never_releases_locks_itself(self) -> None:
        joined = "\n".join(self._code())
        self.assertNotIn(" release ", joined)
        self.assertNotIn("rm -f \"$ONCE", joined)
        self.assertIn("run-verdict", joined)

    def test_watchdog_present_next_to_wrapper(self) -> None:
        self.assertTrue((HOST / "symphony_watchdog.py").is_file())


STUB_TOKEN = """import os, subprocess, sys
args = sys.argv[1:]
assert args[:2] == ["exec", "--"], args
if os.environ.get("STUB_TOKEN_FAIL"):
    raise SystemExit(1)
raise SystemExit(subprocess.call(args[2:]))
"""
STUB_WATCHDOG = """import json, os, sys
from pathlib import Path
a = sys.argv[1:]
out = Path(a[a.index("--stdout-file") + 1])
Path(os.environ["STUB_ARGS"]).write_text("\\n".join(a), encoding="utf-8")
out.write_text(os.environ.get("STUB_OUTPUT", "Rate Limits\\n"), encoding="utf-8")
slots = list(Path(os.environ["STUB_SLOT_DIR"]).iterdir())
Path(os.environ["STUB_SLOTS"]).write_text(str(len(slots)), encoding="utf-8")
reason = os.environ.get("STUB_REASON", "first_run_finished")
if reason != "none":
    print(json.dumps({"watchdog": "started", "pid": 1}), file=sys.stderr)
    print(json.dumps({"watchdog": "stop", "reason": reason}), file=sys.stderr)
    print(json.dumps({"watchdog": "terminated",
                      "clean": os.environ.get("STUB_CLEAN", "1") == "1"}), file=sys.stderr)
raise SystemExit(int(os.environ.get("STUB_RC", "0")))
"""


class WrapperFlowTests(unittest.TestCase):
    """Ganzer Ablauf von run-symphony.sh mit Stubs: kein Proxy, kein Token, kein Symphony."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        for name in ("run-symphony.sh", "bwrap-env.sh"):
            shutil.copy(HOST / name, self.bin / name)
        self.shared = self.base / "research"
        gate = (ROOT / "scripts" / "symphony_dispatch_gate.py").read_text(encoding="utf-8")
        # Pfade sind fest verdrahtet; der Test zeigt sie im kopierten Gate auf ein Temp-Verzeichnis.
        self.assertEqual(gate.count('Path("/workspace/research/'), 5)
        (self.bin / "symphony_dispatch_gate.py").write_text(
            gate.replace('Path("/workspace/research/', f'Path("{self.shared}/'), encoding="utf-8")
        (self.bin / "symphony_app_token.py").write_text(STUB_TOKEN, encoding="utf-8")
        (self.bin / "symphony_watchdog.py").write_text(STUB_WATCHDOG, encoding="utf-8")
        (self.bin / "egress-proxy.sh").write_text(
            '#!/bin/sh\n[ -z "$STUB_PROXY_FAIL" ]\n', encoding="utf-8")
        (self.bin / "egress-proxy.sh").chmod(0o755)
        self.pilot = self.base / "pilot"
        self.pilot.mkdir()
        (self.pilot / "WORKFLOW.md").write_text(
            "---\ngmv:\n  dispatch_gate:\n    max_concurrent: 2\n---\n", encoding="utf-8")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def run_wrapper(self, issue: str, **extra: str):
        env = {**os.environ, "GMV_SYMPHONY_START_APPROVED": "yes", "PILOT_DIR": str(self.pilot),
               "GMV_HOME": str(self.base / "home"), "GMV_SYMPHONY_ISSUE": issue,
               "STUB_SLOT_DIR": str(self.shared / "state" / "slots"),
               "STUB_ARGS": str(self.base / f"args-{issue}"),
               "STUB_SLOTS": str(self.base / f"slots-{issue}"), **extra}
        for var in ("GMV_SHARED_SLOT_DIR", "GMV_SHARED_SLOT_LOCK", "GMV_ALERTS_LOG",
                    "GMV_QUOTA_STOP", "GMV_RUN_STOP", "GMV_MAX_TOTAL_RUNS"):
            if var not in extra:
                env.pop(var, None)
        return subprocess.run(["bash", str(self.bin / "run-symphony.sh")], env=env,
                              capture_output=True, text=True, check=False, timeout=60)

    @property
    def slots(self) -> Path:
        return self.shared / "state" / "slots"

    def alerts(self) -> str:
        return (self.shared / "ALERTS.log").read_text(encoding="utf-8")

    def test_clean_run_holds_slot_and_releases_it(self) -> None:
        proc = self.run_wrapper("21")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual((self.base / "slots-21").read_text(encoding="utf-8"), "1")
        self.assertEqual(list((self.shared / "state" / "slots").iterdir()), [])
        self.assertTrue((self.pilot / "log" / "once" / "issue-21.once").exists())
        args = (self.base / "args-21").read_text(encoding="utf-8").split("\n")
        self.assertEqual(args[args.index("--budget") + 1], "5000000")
        self.assertEqual(args[args.index("--log") + 1], str(self.pilot / "log/issue-21/log"))
        # zweiter Start desselben Issues: blockiert; anderes Issue: läuft
        self.assertEqual(self.run_wrapper("21").returncode, 2)
        self.assertEqual(self.run_wrapper("22").returncode, 0)

    def test_known_guard_stop_rc_is_passed_through(self) -> None:
        proc = self.run_wrapper("23", STUB_RC="1", STUB_REASON="retry_cycle_scheduled")
        self.assertEqual(proc.returncode, 1, proc.stderr)
        self.assertEqual(list(self.slots.iterdir()), [])
        self.assertFalse((self.shared / "state" / "symphony-stop").exists())
        self.assertEqual(self.run_wrapper("26").returncode, 0)

    def test_unknown_outcomes_are_fail_closed(self) -> None:
        cases = {
            "unknown reason": {"STUB_RC": "1", "STUB_REASON": "token_readout_missing"},
            "child crash": {"STUB_RC": "1", "STUB_REASON": "child_exited code=-11"},
            "no verdict": {"STUB_RC": "1", "STUB_REASON": "none"},
            "unclean": {"STUB_RC": "3", "STUB_CLEAN": "0"},
            "token helper fails": {"STUB_TOKEN_FAIL": "1"},
            "proxy fails after once": {"STUB_PROXY_FAIL": "1"},
        }
        stop = self.shared / "state" / "symphony-stop"
        for n, (name, extra) in enumerate(cases.items(), start=60):
            with self.subTest(name=name):
                stop.unlink(missing_ok=True)
                proc = self.run_wrapper(str(n), **extra)
                self.assertEqual(proc.returncode, 13, proc.stderr)
                self.assertTrue(stop.exists())
                self.assertIn(f"issue={n} unknown_fail_closed", self.alerts())
                self.assertEqual(list(self.slots.iterdir()), [])
                self.assertTrue((self.pilot / "log" / "once" / f"issue-{n}.once").exists())
        blocked = self.run_wrapper("70")
        self.assertEqual(blocked.returncode, 13)
        self.assertIn("run_stop_active", blocked.stderr)
        self.assertFalse((self.base / "args-70").exists())

    def test_path_overrides_are_rejected(self) -> None:
        for var in ("GMV_SHARED_SLOT_DIR", "GMV_SHARED_SLOT_LOCK", "GMV_ALERTS_LOG",
                    "GMV_QUOTA_STOP", "GMV_RUN_STOP"):
            with self.subTest(var=var):
                proc = self.run_wrapper("31", **{var: str(self.base / "elsewhere")})
                self.assertEqual(proc.returncode, 2)
                self.assertIn("path_override_forbidden", proc.stderr)
                self.assertFalse((self.base / "args-31").exists())

    def test_max_total_only_lowerable(self) -> None:
        for bad in ("11", "0", "abc"):
            with self.subTest(bad=bad):
                proc = self.run_wrapper("32", GMV_MAX_TOTAL_RUNS=bad)
                self.assertEqual(proc.returncode, 2)
                self.assertIn("max_total_runs_invalid", proc.stderr)
        self.slots.mkdir(parents=True, exist_ok=True)
        (self.slots / str(os.getpid())).write_text("pid=x reserved=0 id=t\n", encoding="utf-8")
        proc = self.run_wrapper("33", GMV_MAX_TOTAL_RUNS="1")
        self.assertEqual(proc.returncode, 5, proc.stderr)
        self.assertIn("shared_limit_reached", proc.stderr)
        self.assertFalse((self.pilot / "log" / "once" / "issue-33.once").exists())

    def test_quota_stop_marker_blocks_start(self) -> None:
        (self.shared / "state").mkdir(parents=True)
        (self.shared / "state" / "quota-stop").write_text("x\n", encoding="utf-8")
        proc = self.run_wrapper("44")
        self.assertEqual(proc.returncode, 9)
        self.assertIn("quota_stop_active", proc.stderr)
        self.assertFalse((self.pilot / "log" / "once" / "issue-44.once").exists())

    def test_quota_hit_is_fail_closed_for_all_issues(self) -> None:
        proc = self.run_wrapper("24", STUB_OUTPUT="error: usage_limit_reached\n", STUB_RC="1")
        self.assertEqual(proc.returncode, 9, proc.stderr)
        alerts = (self.shared / "ALERTS.log").read_text(encoding="utf-8")
        self.assertIn("issue=24 quota_fail_closed reason=quota_exhausted", alerts)
        self.assertTrue((self.shared / "state" / "quota-stop").exists())
        self.assertEqual(list((self.shared / "state" / "slots").iterdir()), [])
        nxt = self.run_wrapper("25")
        self.assertEqual(nxt.returncode, 9)
        self.assertFalse((self.base / "args-25").exists())  # nichts gestartet


if __name__ == "__main__":
    unittest.main()
