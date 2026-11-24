"""Tests for the external Symphony watchdog (ENG-003).

Synthetic logs only (fictitious issue numbers), a dummy process with a grandchild,
no Symphony, no network, no tokens. Ported from the host suite
``watchdog-tests/run_tests.sh``; the two replays of real pilot logs stay on the
host because those logs are not committed.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts" / "symphony_host"))
import symphony_watchdog as wd  # noqa: E402

WATCHDOG = ROOT / "scripts" / "symphony_host" / "symphony_watchdog.py"
DUMMY = ROOT / "tests" / "fixtures" / "symphony_watchdog_dummy.py"

D87 = "x info: Dispatching issue to agent: issue_id=87 issue_identifier=GH-87"


def _alive(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return state != "Z"


def run_watchdog(tmp: Path, name: str, log_lines: list[str] | None, *, stdout_lines=None,
                 ignore_term: bool = False, delay: float = 0.05, extra: list[str] | None = None,
                 command: list[str] | None = None):
    log = tmp / f"{name}.log"
    log.write_text("")
    src = "-"
    if log_lines is not None:
        (tmp / f"{name}.src").write_text("\n".join(log_lines) + "\n")
        src = str(tmp / f"{name}.src")
    out_src = "-"
    if stdout_lines is not None:
        (tmp / f"{name}.stdout").write_text("\n".join(stdout_lines) + "\n")
        out_src = str(tmp / f"{name}.stdout")
    cmd = command or [sys.executable, str(DUMMY), str(log), out_src, src,
                      "1" if ignore_term else "0", str(delay)]
    proc = subprocess.run(
        [sys.executable, str(WATCHDOG), "--log", str(log), "--stdout-file",
         str(tmp / f"{name}.out"), "--log-from-start", "--grace", "2", "--poll", "0.05",
         *(extra or []), "--", *cmd],
        capture_output=True, text=True, timeout=60, check=False)
    events = [json.loads(ln) for ln in proc.stderr.splitlines() if ln.startswith("{")]
    stop = next(e for e in events if e["watchdog"] == "stop")
    term = next(e for e in events if e["watchdog"] == "terminated")
    m = re.search(r"GRANDCHILD (\d+)", proc.stderr)
    grandchild_alive = bool(m) and _alive(int(m.group(1)))
    return proc.returncode, stop, term, grandchild_alive, events


@pytest.mark.parametrize(
    ("name", "lines", "reason"),
    [
        ("second_dispatch", [D87, D87], "second_dispatch"),
        ("second_issue",
         [D87, "x info: Starting agent run for issue_id=88 issue_identifier=GH-88"],
         "second_issue"),
        ("retry",
         ["x info: Dispatching issue to agent: issue_id=87",
          "x warning: Retrying issue_id=87 issue_identifier=GH-87 in 1000ms (attempt 1)"],
         "retry_cycle_scheduled"),
        ("loop",
         ["x info: Dispatching issue to agent: issue_id=87",
          *[f"x info: Codex session started for issue_id=87 s={i}" for i in range(1, 5)]],
         "loop_sessions"),
    ],
)
def test_stops_tree_on_violation(tmp_path: Path, name, lines, reason) -> None:
    rc, stop, term, gc_alive, _ = run_watchdog(tmp_path, name, lines)
    assert stop["reason"].startswith(reason)
    assert rc == 1
    assert term["clean"] is True
    assert gc_alive is False


def test_first_run_finished_is_success(tmp_path: Path) -> None:
    rc, stop, term, gc_alive, _ = run_watchdog(
        tmp_path, "finished",
        [D87, "x info: Codex session started for issue_id=87",
         "x info: Agent task finished for issue_id=87 issue_identifier=GH-87"])
    assert stop["reason"] == "first_run_finished"
    assert (rc, term["clean"], gc_alive) == (0, True, False)


def test_token_budget_stop(tmp_path: Path) -> None:
    dash = [f"│ Tokens: in {n:,} | out 10 | total {n + 10:,}" for n in
            (100_000, 900_000, 4_699_995, 4_800_000, 5_500_000)]
    rc, stop, term, gc_alive, _ = run_watchdog(
        tmp_path, "budget", None, stdout_lines=dash, delay=0.05)
    assert stop["reason"].startswith("token_budget_reached")
    assert stop["tokens"] >= 4_700_000  # Standard: 5_000_000 - 300_000
    assert (rc, term["clean"], gc_alive) == (1, True, False)


def test_sigterm_ignored_escalates_to_sigkill(tmp_path: Path) -> None:
    rc, stop, term, gc_alive, events = run_watchdog(
        tmp_path, "sigterm", [D87, D87], ignore_term=True)
    assert stop["reason"].startswith("second_dispatch")
    signals = [e["signal"] for e in events if e["watchdog"] == "signal_sent"]
    assert signals == ["SIGTERM", "SIGKILL"]
    assert (rc, term["clean"], gc_alive) == (1, True, False)


def test_missing_token_readout_fails_closed(tmp_path: Path) -> None:
    cmd = [sys.executable, "-c",
           "import subprocess,sys,time; p=subprocess.Popen(['sleep','600']);"
           "print('GRANDCHILD',p.pid,file=sys.stderr,flush=True); time.sleep(600)"]
    rc, stop, term, gc_alive, _ = run_watchdog(
        tmp_path, "notokens", None, extra=["--no-token-readout", "1"], command=cmd)
    assert stop["reason"] == "token_readout_missing"
    assert (rc, term["clean"], gc_alive) == (1, True, False)


def test_max_runtime(tmp_path: Path) -> None:
    rc, stop, term, gc_alive, _ = run_watchdog(
        tmp_path, "runtime", None, extra=["--max-runtime", "1"])
    assert stop["reason"] == "max_runtime"
    assert (rc, term["clean"], gc_alive) == (1, True, False)


def test_directory_mode_ignores_old_rotated_content(tmp_path: Path) -> None:
    logdir = tmp_path / "logdir"
    logdir.mkdir()
    (logdir / "symphony.log.1").write_text("\n".join([D87] * 5) + "\n")
    src = tmp_path / "retry.src"
    src.write_text("x info: Dispatching issue to agent: issue_id=87\n"
                   "x warning: Retrying issue_id=87 issue_identifier=GH-87 in 1000ms\n")
    proc = subprocess.run(
        [sys.executable, str(WATCHDOG), "--log", str(logdir), "--stdout-file",
         str(tmp_path / "dir.out"), "--grace", "2", "--poll", "0.05", "--",
         sys.executable, str(DUMMY), str(logdir / "symphony.log.2"), "-", str(src), "0", "0.3"],
        capture_output=True, text=True, timeout=60, check=False)
    stop = next(json.loads(ln) for ln in proc.stderr.splitlines()
                if ln.startswith("{") and '"stop"' in ln)
    assert stop["reason"] == "retry_cycle_scheduled"
    assert stop["dispatches"] == 1


def test_rules_reject_invalid_budget() -> None:
    with pytest.raises(ValueError):
        wd.Rules(budget=100, reserve=100, max_sessions=3)


def test_dashboard_redraw_never_counts_backwards() -> None:
    rules = wd.Rules(budget=2_000_000, reserve=300_000, max_sessions=3)
    assert rules.on_stdout("Tokens: in 1,000 | out 0 | total 1,000") is None
    assert rules.on_stdout("Tokens: in 10 | out 0 | total 10") is None
    assert rules.tokens == 1_000


def test_watchdog_never_prints_environment(tmp_path: Path) -> None:
    env = {**os.environ, "GITHUB_TOKEN": "ghs_dummyvalue_not_real"}
    proc = subprocess.run(
        [sys.executable, str(WATCHDOG), "--log", str(tmp_path / "x.log"), "--stdout-file",
         str(tmp_path / "x.out"), "--log-from-start", "--grace", "1", "--poll", "0.05",
         "--max-runtime", "0.5", "--", sys.executable, "-c", "import time; time.sleep(30)"],
        capture_output=True, text=True, env=env, timeout=30, check=False)
    assert "ghs_dummyvalue_not_real" not in proc.stderr + proc.stdout
