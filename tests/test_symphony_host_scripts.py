"""Static and argument tests for the Symphony host wrapper (no bwrap needed)."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
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
            "quota-check", "trap release_slot EXIT", "slot-acquire", "prepare-run",
            "once-acquire", 'proxy-start --proxy-script "$HERE/egress-proxy.sh"',
            'python3 "$TOKEN_PY" exec', "quota-scan")]
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
STUB_WATCHDOG = """import json, os, sys, time
from pathlib import Path
a = sys.argv[1:]
out = Path(a[a.index("--stdout-file") + 1])
Path(os.environ["STUB_ARGS"]).write_text("\\n".join(a), encoding="utf-8")
out.write_text(os.environ.get("STUB_OUTPUT", "Rate Limits\\n"), encoding="utf-8")
time.sleep(float(os.environ.get("STUB_SLEEP", "0")))
# Schreibpfade, die Symphony nutzen würde: logs-root und workspace.root der WORKFLOW.md
logs_root = Path(a[a.index("--logs-root") + 1])
(logs_root / "log").mkdir(parents=True, exist_ok=True)
(logs_root / "log" / "symphony.log").write_text("stub\\n", encoding="utf-8")
wf = Path(a[-1]).read_text(encoding="utf-8")
root = Path(next(ln.split(": ", 1)[1] for ln in wf.splitlines() if ln.startswith("  root: ")))
(root / "GMV-1").mkdir(parents=True, exist_ok=True)
(root / "GMV-1" / "x.txt").write_text("stub\\n", encoding="utf-8")
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


def pilot_workflow(max_concurrent: int) -> str:
    return (
        "---\ntracker:\n  kind: github\n  required_labels:\n    - gmv-symphony-pilot\n"
        "workspace:\n  # Kommentar\n  root: /workspace/symphony-pilot/workspaces\n"
        f"gmv:\n  dispatch_gate:\n    max_concurrent: {max_concurrent}\n---\nPrompt\n"
    )


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
        (self.pilot / "WORKFLOW.md").write_text(pilot_workflow(2), encoding="utf-8")

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
        run_dir = self.pilot / "runs" / "issue-21"
        self.assertEqual(args[args.index("--log") + 1], str(run_dir / "log" / "log"))
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


    # --- Samira, Bedingung 1: Tracker- und Zustandstrennung je Issue -----------------

    def _snapshot(self) -> dict[str, tuple[int, int]]:
        out = {}
        for root in (self.pilot, self.shared):
            for f in root.rglob("*"):
                if f.is_file():
                    st = f.stat()
                    out[str(f)] = (st.st_ino, st.st_mtime_ns)
        return out

    def start_wrapper(self, issue: str, **extra: str) -> subprocess.Popen:
        env = {**os.environ, "GMV_SYMPHONY_START_APPROVED": "yes", "PILOT_DIR": str(self.pilot),
               "GMV_HOME": str(self.base / "home"), "GMV_SYMPHONY_ISSUE": issue,
               "STUB_SLOT_DIR": str(self.slots),
               "STUB_ARGS": str(self.base / f"args-{issue}"),
               "STUB_SLOTS": str(self.base / f"slots-{issue}"), **extra}
        for var in ("GMV_SHARED_SLOT_DIR", "GMV_SHARED_SLOT_LOCK", "GMV_ALERTS_LOG",
                    "GMV_QUOTA_STOP", "GMV_RUN_STOP", "GMV_MAX_TOTAL_RUNS"):
            env.pop(var, None)
        return subprocess.Popen(["bash", str(self.bin / "run-symphony.sh")], env=env,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    def test_two_parallel_slots_have_separate_tracker_and_state(self) -> None:
        before = self._snapshot()
        procs = {n: self.start_wrapper(n, STUB_SLEEP="2") for n in ("31", "32")}
        for n, proc in procs.items():
            _, err = proc.communicate(timeout=60)
            self.assertEqual(proc.returncode, 0, err)
            # beide liefen gleichzeitig: jeder sah zwei Symphony-Slots
            self.assertEqual((self.base / f"slots-{n}").read_text(encoding="utf-8"), "2")
        self.assertEqual(list(self.slots.iterdir()), [])
        roots = set()
        for n in ("31", "32"):
            run_dir = self.pilot / "runs" / f"issue-{n}"
            wf = (run_dir / "WORKFLOW.md").read_text(encoding="utf-8")
            self.assertIn("    - gmv-symphony-pilot\n    - gmv-symphony-issue-" + n + "\n", wf)
            self.assertIn(f"  root: {run_dir / 'workspaces'}\n", wf)
            self.assertTrue((run_dir / "workspaces" / "GMV-1" / "x.txt").exists())
            args = (self.base / f"args-{n}").read_text(encoding="utf-8").split("\n")
            i = args.index("--chdir")
            self.assertEqual(args[i - 6:i + 2], [
                "--ro-bind", str(self.pilot), str(self.pilot),
                "--bind", str(run_dir), str(run_dir), "--chdir", str(run_dir)])
            self.assertEqual(args[-1], str(run_dir / "WORKFLOW.md"))
            self.assertEqual(args[args.index("--logs-root") + 1], str(run_dir / "log"))
            self.assertEqual(args[args.index("--stdout-file") + 1], str(run_dir / "run.out"))
            roots.add(wf)
        self.assertEqual(len(roots), 2)
        # Schreibpfad-Inventar: alles Geschriebene liegt im eigenen Lauf-Verzeichnis
        # oder ist eine der flock-/O_EXCL-geschützten gemeinsamen Dateien.
        after = self._snapshot()
        written = {f for f, v in after.items() if before.get(f) != v}
        allowed_shared = {
            str(self.pilot / "log" / "once" / "issue-31.once"),
            str(self.pilot / "log" / "once" / "issue-32.once"),
            str(self.shared / ".research.lock"),
        }
        per_issue = {n: str(self.pilot / "runs" / f"issue-{n}") + "/" for n in ("31", "32")}
        stray = [f for f in written if f not in allowed_shared
                 and not any(f.startswith(d) for d in per_issue.values())]
        self.assertEqual(stray, [])
        self.assertTrue(any(f.startswith(per_issue["31"]) for f in written))
        self.assertTrue(any(f.startswith(per_issue["32"]) for f in written))

    def test_template_limit_one_blocks_second_parallel_slot(self) -> None:
        (self.pilot / "WORKFLOW.md").write_text(pilot_workflow(1), encoding="utf-8")
        first = self.start_wrapper("33", STUB_SLEEP="3")
        deadline = time.monotonic() + 20
        while not (self.slots.exists() and any(self.slots.iterdir())):
            self.assertLess(time.monotonic(), deadline)
            time.sleep(0.05)
        second = self.run_wrapper("34")
        self.assertEqual(second.returncode, 5, second.stderr)
        self.assertFalse((self.pilot / "runs" / "issue-34").exists())
        _, err = first.communicate(timeout=60)
        self.assertEqual(first.returncode, 0, err)

    def _assert_only_this_start_ended(self, proc, issue: str) -> None:
        """Samira, Review #149, Auflage 1: fester rc=2, kein globaler Stopp, keine Sperre."""
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn("nur dieser Start endet", proc.stderr)
        self.assertFalse((self.shared / "state" / "symphony-stop").exists())
        self.assertFalse((self.shared / "state" / "quota-stop").exists())
        self.assertFalse((self.shared / "ALERTS.log").exists())
        self.assertFalse((self.pilot / "log" / "once" / f"issue-{issue}.once").exists())
        self.assertFalse((self.base / f"args-{issue}").exists())  # nichts gestartet
        self.assertEqual(list(self.slots.iterdir()), [])

    def test_existing_run_dir_ends_only_this_start_rc2_without_run_stop(self) -> None:
        stale = self.pilot / "runs" / "issue-35"
        stale.mkdir(parents=True)
        proc = self.run_wrapper("35")
        self.assertIn("run_dir_exists", proc.stderr)
        self._assert_only_this_start_ended(proc, "35")
        # andere Issues starten weiter (kein symphony-stop)
        self.assertEqual(self.run_wrapper("38").returncode, 0)
        # nach Aufräumen startet auch dieses Issue (keine Einmal-Sperre gesetzt)
        stale.rmdir()
        self.assertEqual(self.run_wrapper("35").returncode, 0)

    def test_unexpected_workflow_ends_only_this_start_rc2_without_run_stop(self) -> None:
        (self.pilot / "WORKFLOW.md").write_text(
            pilot_workflow(2).replace("  required_labels:\n    - gmv-symphony-pilot\n", ""),
            encoding="utf-8")
        proc = self.run_wrapper("37")
        self.assertIn("workflow_structure_unexpected", proc.stderr)
        self._assert_only_this_start_ended(proc, "37")
        self.assertFalse((self.pilot / "runs" / "issue-37").exists())  # kein halbes Verzeichnis

    def test_failure_after_once_acquire_stays_fail_closed(self) -> None:
        # Gegenprobe: Abbruch NACH der Einmal-Sperre (Proxy) bleibt rc=13 + symphony-stop.
        proc = self.run_wrapper("39", STUB_PROXY_FAIL="1")
        self.assertEqual(proc.returncode, 13, proc.stderr)
        self.assertTrue((self.shared / "state" / "symphony-stop").exists())

    def test_proxy_start_runs_under_slot_lock(self) -> None:
        log = self.base / "proxy-calls"
        (self.bin / "egress-proxy.sh").write_text(
            f'#!/bin/sh\nflock -n {self.shared}/.research.lock true && echo free >>{log} '
            f'|| echo locked >>{log}\n', encoding="utf-8")
        proc = self.run_wrapper("36")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(log.read_text(encoding="utf-8"), "locked\n")


# --- Samira, Bedingung 2: run-wave.sh stoppt den Proxy nur ohne lebenden Slot -----------

STUB_GH = """#!/bin/sh
echo "$*" >> "$STUB_GH_LOG"
"""


class RunWaveTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.pilot = self.base / "pilot"
        (self.pilot / "bin").mkdir(parents=True)
        self.shared = self.base / "research"
        gate = (ROOT / "scripts" / "symphony_dispatch_gate.py").read_text(encoding="utf-8")
        (self.pilot / "bin" / "symphony_dispatch_gate.py").write_text(
            gate.replace('Path("/workspace/research/', f'Path("{self.shared}/'), encoding="utf-8")
        self.calls = self.base / "proxy-calls"
        proxy = self.pilot / "bin" / "egress-proxy.sh"
        proxy.write_text(f'#!/bin/sh\necho "$1" >> {self.calls}\n', encoding="utf-8")
        proxy.chmod(0o755)
        one = self.pilot / "pilot-one-run.sh"
        one.write_text('#!/bin/sh\necho "run $1"\nexit "${STUB_RUN_RC:-0}"\n', encoding="utf-8")
        one.chmod(0o755)
        self.fake = self.base / "fakebin"
        self.fake.mkdir()
        (self.fake / "gh").write_text(STUB_GH, encoding="utf-8")
        (self.fake / "gh").chmod(0o755)
        self.gh_log = self.base / "gh.log"
        self.children: list[subprocess.Popen] = []

    def tearDown(self) -> None:
        for c in self.children:
            c.kill()
            c.wait()
        self._tmp.cleanup()

    def wave(self, issue: str, **extra: str) -> subprocess.CompletedProcess:
        env = {**os.environ, "PILOT_DIR": str(self.pilot), "GMV_WAVE_LABEL_DELAY": "0",
               "STUB_GH_LOG": str(self.gh_log),
               "PATH": f"{self.fake}:{os.environ['PATH']}", **extra}
        return subprocess.run(["bash", str(HOST / "run-wave.sh"), issue], env=env,
                              capture_output=True, text=True, check=False, timeout=60)

    def live_symphony_slot(self, issue: int) -> None:
        child = subprocess.Popen(["sleep", "60"])
        self.children.append(child)
        slots = self.shared / "state" / "slots"
        slots.mkdir(parents=True, exist_ok=True)
        (slots / str(child.pid)).write_text(
            f"pid={child.pid} reserved=0 id=symphony-issue-{issue} kind=symphony issue={issue}\n",
            encoding="utf-8")

    def test_idle_stops_proxy_and_sets_issue_labels(self) -> None:
        proc = self.wave("41")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(self.calls.read_text(encoding="utf-8"), "stop\n")
        gh = self.gh_log.read_text(encoding="utf-8")
        self.assertIn("--add-label gmv-symphony-pilot --add-label gmv-symphony-issue-41", gh)
        self.assertIn("--remove-label gmv-symphony-issue-41", gh)
        self.assertIn("run 41", proc.stdout)

    def test_run_rc_is_passed_through_after_idle_stop(self) -> None:
        proc = self.wave("42", STUB_RUN_RC="13")
        self.assertEqual(proc.returncode, 13)
        self.assertEqual(self.calls.read_text(encoding="utf-8"), "stop\n")

    def test_live_symphony_slot_keeps_proxy_rc14_and_alert(self) -> None:
        self.live_symphony_slot(77)
        proc = self.wave("43")
        self.assertEqual(proc.returncode, 14, proc.stderr)
        self.assertFalse(self.calls.exists())  # kein Stopp
        alerts = (self.shared / "ALERTS.log").read_text(encoding="utf-8")
        self.assertIn("ALERT run-wave issue=43 proxy_stop_refused live_symphony_slots=1 issues=77",
                      alerts)
        self.assertEqual(oct((self.shared / "ALERTS.log").stat().st_mode & 0o777), "0o600")

    def test_research_slot_alone_does_not_block_proxy_stop(self) -> None:
        child = subprocess.Popen(["sleep", "60"])
        self.children.append(child)
        slots = self.shared / "state" / "slots"
        slots.mkdir(parents=True)
        (slots / str(child.pid)).write_text(f"pid={child.pid} reserved=0 id=r1\n", encoding="utf-8")
        self.assertEqual(self.wave("44").returncode, 0)
        self.assertEqual(self.calls.read_text(encoding="utf-8"), "stop\n")

    def test_invalid_issue_or_existing_run_dir_aborts_before_labels(self) -> None:
        self.assertEqual(self.wave("abc").returncode, 20)
        (self.pilot / "runs" / "issue-45").mkdir(parents=True)
        self.assertEqual(self.wave("45").returncode, 20)
        self.assertFalse(self.gh_log.exists())
        self.assertFalse(self.calls.exists())



# --- Samira, Review #149, Auflage 3: pilot-one-run.sh und Selbsttest als geprüfte Vorlage ---

STUB_GH_PY = """#!/usr/bin/env python3
import os, re, sys
a = sys.argv[1:]
with open(os.environ["STUB_GH_LOG"], "a", encoding="utf-8") as fh:
    fh.write(" ".join(a) + "\\n")
if a[0] == "api":
    m = re.search(r"labels=gmv-symphony-issue-(\\d+)", a[1])
    if m:
        print(os.environ.get("STUB_GH_LABELED", m.group(1)))
    else:
        n = a[1].rsplit("/", 1)[1]
        print(os.environ.get("STUB_GH_LABELS",
                             f"bug,gmv-symphony-pilot,gmv-symphony-issue-{n}"))
"""

SELFTEST_OK = "\n".join([
    "== 1 außerhalb", "== 2 bwrap-Namespace", "worker.pem: fehlt", "hosts.yml: fehlt",
    "WRITE erlaubt: ./probe.txt", "WRITE verweigert: ../SELFTEST-B/probe.txt",
    "WRITE verweigert: /tmp/probe.txt", "WRITE verweigert: /home/box/probe.txt",
    "NET https://github.com/ -> 200", "NET https://api.github.com/zen -> 200",
    "NET https://api.openai.com/v1/models -> 401", "NET https://example.com/ -> 000",
    "NET https://pypi.org/simple/ -> 000"])

# Stub für bin/run-symphony.sh: belegt wie das Original einen Symphony-Slot im
# gemeinsamen Zähler (eigene PID), hält ihn STUB_HOLD Sekunden, gibt ihn frei.
STUB_RUN_SYMPHONY = """#!/usr/bin/env bash
echo "issue=$GMV_SYMPHONY_ISSUE approved=$GMV_SYMPHONY_START_APPROVED" >> "$STUB_RUNS_LOG"
mkdir -p "$STUB_SLOT_DIR"
I=$GMV_SYMPHONY_ISSUE
echo "pid=$$ reserved=0 id=symphony-issue-$I kind=symphony issue=$I" > "$STUB_SLOT_DIR/$$"
sleep "${STUB_HOLD:-0}"
rm -f "$STUB_SLOT_DIR/$$"
exit "${STUB_RS:-0}"
"""


class PilotOneRunTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.pilot = self.base / "pilot"
        self.bin = self.pilot / "bin"
        self.bin.mkdir(parents=True)
        self.shared = self.base / "research"
        gate = (ROOT / "scripts" / "symphony_dispatch_gate.py").read_text(encoding="utf-8")
        (self.bin / "symphony_dispatch_gate.py").write_text(
            gate.replace('Path("/workspace/research/', f'Path("{self.shared}/'), encoding="utf-8")
        self.calls = self.base / "proxy-calls"
        self._exe(self.bin / "egress-proxy.sh",
                  f'#!/bin/sh\nif [ "$1" = status ]; then echo läuft; exit 0; fi\n'
                  f'flock -n {self.shared}/.research.lock true && echo "$1 free" >>{self.calls} '
                  f'|| echo "$1 locked" >>{self.calls}\n')
        self._exe(self.bin / "sandbox-selftest.sh",
                  '#!/bin/sh\n[ -n "$STUB_SELFTEST_FAIL" ] && exit 1\ncat <<EOF\n'
                  + SELFTEST_OK + "\nEOF\n")
        self._exe(self.bin / "run-symphony.sh", STUB_RUN_SYMPHONY)
        for name in ("pilot-one-run.sh", "run-wave.sh"):
            shutil.copy(HOST / name, self.pilot / name)
        self.fake = self.base / "fakebin"
        self.fake.mkdir()
        self._exe(self.fake / "gh", STUB_GH_PY)
        self.gh_log = self.base / "gh.log"
        self.runs_log = self.base / "runs.log"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    @staticmethod
    def _exe(path: Path, text: str) -> None:
        path.write_text(text, encoding="utf-8")
        path.chmod(0o755)

    def env(self, **extra: str) -> dict[str, str]:
        env = {**os.environ, "PILOT_DIR": str(self.pilot), "GMV_WAVE_LABEL_DELAY": "0",
               "STUB_GH_LOG": str(self.gh_log), "STUB_RUNS_LOG": str(self.runs_log),
               "STUB_SLOT_DIR": str(self.shared / "state" / "slots"),
               "PATH": f"{self.fake}:{os.environ['PATH']}", **extra}
        for var in ("GMV_SHARED_SLOT_DIR", "GMV_SHARED_SLOT_LOCK", "GMV_ALERTS_LOG",
                    "GMV_QUOTA_STOP", "GMV_RUN_STOP", "GMV_MAX_TOTAL_RUNS"):
            env.pop(var, None)
        return env

    def one_run(self, issue: str, **extra: str) -> subprocess.CompletedProcess:
        return subprocess.run(["bash", str(self.pilot / "pilot-one-run.sh"), issue],
                              env=self.env(**extra), capture_output=True, text=True,
                              check=False, timeout=60)

    def test_happy_path_exit_is_run_rc_not_process_count(self) -> None:
        proc = self.one_run("51")
        # 2b: früher rc=1 aus der Prozesszählung der letzten Zeile, jetzt rc des Laufs
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertRegex(proc.stdout, r"Symphony/Codex-Prozesse danach: \d+\n\Z")
        self.assertEqual(self.runs_log.read_text(encoding="utf-8"), "issue=51 approved=yes\n")
        self.assertEqual(self.calls.read_text(encoding="utf-8"), "start locked\n")
        gh = self.gh_log.read_text(encoding="utf-8")
        self.assertIn("labels=gmv-symphony-issue-51&state=open", gh)
        self.assertIn("issue edit 51 -R tiktokagentur-art/gmv-foundation "
                      "--remove-label gmv-symphony-pilot", gh)
        self.assertTrue(list((self.pilot / "log").glob("selftest-51-*.txt")))

    def test_run_rc_is_passed_through(self) -> None:
        for rs in ("2", "5", "9", "13"):
            with self.subTest(rs=rs):
                proc = self.one_run("52", STUB_RS=rs)
                self.assertEqual(proc.returncode, int(rs), proc.stdout)
                self.assertIn(f"run-symphony rc={rs}", proc.stdout)

    def test_live_symphony_slot_and_processes_do_not_block_other_issue(self) -> None:
        slots = self.shared / "state" / "slots"
        slots.mkdir(parents=True)
        other = subprocess.Popen(["bash", "-c", "exec -a symphony-nightly-test sleep 60"])
        try:
            (slots / str(other.pid)).write_text(
                f"pid={other.pid} reserved=0 id=symphony-issue-60 kind=symphony issue=60\n",
                encoding="utf-8")
            proc = self.one_run("53")
        finally:
            other.kill()
            other.wait()
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertIn("issue=53", self.runs_log.read_text(encoding="utf-8"))

    def test_label_checks_abort_before_proxy_and_run(self) -> None:
        cases = {
            "ohne Issue-Label": {"STUB_GH_LABELS": "gmv-symphony-pilot"},
            "ohne Pilot-Label": {"STUB_GH_LABELS": "gmv-symphony-issue-54"},
            "geschlossen": {"STUB_GH_LABELS": ""},
            "Label doppelt": {"STUB_GH_LABELED": "54,77"},
            "falsches Label-Präfix": {
                "STUB_GH_LABELS": "gmv-symphony-pilot,gmv-symphony-issue-540"},
        }
        for name, extra in cases.items():
            with self.subTest(name):
                proc = self.one_run("54", **extra)
                self.assertEqual(proc.returncode, 10, proc.stdout)
                self.assertFalse(self.calls.exists())
                self.assertFalse(self.runs_log.exists())
        self.assertEqual(self.one_run("0").returncode, 10)

    def test_selftest_failure_aborts_before_run(self) -> None:
        proc = self.one_run("55", STUB_SELFTEST_FAIL="1")
        self.assertEqual(proc.returncode, 12)
        self.assertFalse(self.runs_log.exists())

    def test_two_parallel_waves_stop_proxy_only_after_last_slot(self) -> None:
        # live-run-wave stoppte unbedingt; jetzt: früher endende Welle rc=14 + ALERT, kein Stopp
        waves = {}
        for issue, hold in (("56", "1"), ("57", "4")):
            waves[issue] = subprocess.Popen(
                ["bash", str(self.pilot / "run-wave.sh"), issue],
                env=self.env(STUB_HOLD=hold), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True)
            time.sleep(0.3)
        out = {n: w.communicate(timeout=60) for n, w in waves.items()}
        self.assertEqual(waves["56"].returncode, 14, out["56"])
        self.assertEqual(waves["57"].returncode, 0, out["57"])
        alerts = (self.shared / "ALERTS.log").read_text(encoding="utf-8")
        self.assertIn("ALERT run-wave issue=56 proxy_stop_refused live_symphony_slots=1 issues=57",
                      alerts)
        calls = self.calls.read_text(encoding="utf-8").splitlines()
        self.assertEqual(calls.count("stop locked"), 1)  # genau einmal, unter dem Lock
        self.assertEqual(calls[-1], "stop locked")
        self.assertTrue(all(c.endswith(" locked") for c in calls))
        gh = self.gh_log.read_text(encoding="utf-8")
        for n in ("56", "57"):
            self.assertIn(f"--add-label gmv-symphony-pilot --add-label gmv-symphony-issue-{n}", gh)

    def test_templates_have_no_unlocked_proxy_start_or_exclusive_checks(self) -> None:
        for name in ("pilot-one-run.sh", "sandbox-selftest.sh", "run-wave.sh"):
            text = (HOST / name).read_text(encoding="utf-8")
            code = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith("#"))
            with self.subTest(name):
                self.assertNotRegex(code, r"egress-proxy\.sh\"? (start|stop)")
                self.assertNotIn("-eq 0 ] ||", code)  # kein „0 Prozesse“-Abbruch
                self.assertNotIn("labels=gmv-symphony-pilot&", code)  # keine Pilot-Exklusivität
        selftest = (HOST / "sandbox-selftest.sh").read_text(encoding="utf-8")
        self.assertIn('proxy-start --proxy-script "$HERE/egress-proxy.sh"', selftest)
        self.assertNotIn("workspaces/SELFTEST", selftest)
        self.assertIn('mktemp -d "$PILOT_DIR/selftest/run-XXXXXX"', selftest)
        one = (HOST / "pilot-one-run.sh").read_text(encoding="utf-8")
        self.assertTrue(one.rstrip().endswith('exit "$RS"'))


class SelftestProxyLockTests(unittest.TestCase):
    """sandbox-selftest.sh bis zum Proxy-Start: Start nur über das Gate unter dem Lock."""

    def test_selftest_starts_proxy_under_lock_and_stops_on_gate_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            b = base / "bin"
            b.mkdir()
            for name in ("sandbox-selftest.sh", "bwrap-env.sh"):
                shutil.copy(HOST / name, b / name)
            shared = base / "research"
            gate = (ROOT / "scripts" / "symphony_dispatch_gate.py").read_text(encoding="utf-8")
            (b / "symphony_dispatch_gate.py").write_text(
                gate.replace('Path("/workspace/research/', f'Path("{shared}/'),
                encoding="utf-8")
            calls = base / "calls"
            # Proxy-Stub meldet Fehler: der Selbsttest muss vor bwrap abbrechen.
            (b / "egress-proxy.sh").write_text(
                f'#!/bin/sh\nflock -n {shared}/.research.lock true && echo "$1 free" >>{calls} '
                f'|| echo "$1 locked" >>{calls}\nexit 1\n', encoding="utf-8")
            (b / "egress-proxy.sh").chmod(0o755)
            pilot = base / "pilot"
            pilot.mkdir()
            env = {**os.environ, "PILOT_DIR": str(pilot), "GMV_HOME": str(base / "home")}
            for var in ("GMV_SHARED_SLOT_DIR", "GMV_SHARED_SLOT_LOCK", "GMV_ALERTS_LOG",
                        "GMV_QUOTA_STOP", "GMV_RUN_STOP"):
                env.pop(var, None)
            proc = subprocess.run(["bash", str(b / "sandbox-selftest.sh")], env=env,
                                  capture_output=True, text=True, check=False, timeout=60)
            self.assertNotEqual(proc.returncode, 0)
            self.assertEqual(calls.read_text(encoding="utf-8"), "start locked\n")
            self.assertNotIn("== 1 außerhalb", proc.stdout)  # nichts weiter ausgeführt
            self.assertFalse((pilot / "selftest").exists())


if __name__ == "__main__":
    unittest.main()
