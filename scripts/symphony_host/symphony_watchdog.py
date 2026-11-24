#!/usr/bin/env python3
"""External watchdog for exactly one Symphony pilot run (ENG-003).

Starts the given command (Symphony inside bwrap) as a child, tees its stdout
(status dashboard) to a file, tails the Symphony log, and stops the whole
process tree with SIGTERM (SIGKILL after a grace period) as soon as

- cumulative tokens >= budget - reserve        (default 2_000_000 - 300_000),
- a second dispatch starts (same or other issue), a retry cycle is scheduled,
  or a second issue appears,
- the first agent run has finished (job done, no further cycle),
- a loop is detectable (more Codex sessions than max_turns, or no progress),
- the wall-clock limit is reached,
- token usage cannot be read for too long (fail-closed).

After stopping it verifies that no process of the tree is left. It never
prints environment variables, tokens or log payloads; only event codes.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
TOKENS = re.compile(r"Tokens:\s*in\s*([\d,]+)\s*\|\s*out\s*([\d,]+)\s*\|\s*total\s*([\d,]+)")
DISPATCH = re.compile(r"Dispatching issue to agent: issue_id=(\S+)")
RETRY = re.compile(r"Retrying issue_id=(\S+)")
FINISHED = re.compile(r"Agent task finished for issue_id=(\S+)|Reached agent\.max_turns")
SESSION = re.compile(r"Codex session started for issue_id=(\S+)")
START_RUN = re.compile(r"Starting agent run for issue_id=(\S+)")


def log(event: str, **fields: object) -> None:
    print(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "watchdog": event, **fields}),
          file=sys.stderr, flush=True)


class Rules:
    def __init__(self, budget: int, reserve: int, max_sessions: int) -> None:
        if budget <= 0 or reserve < 0 or reserve >= budget:
            raise ValueError("invalid budget/reserve")
        self.stop_at = budget - reserve
        self.max_sessions = max_sessions
        self.tokens = 0
        self.issue: str | None = None
        self.dispatches = 0
        self.sessions = 0

    def on_stdout(self, line: str) -> str | None:
        m = TOKENS.search(ANSI.sub("", line))
        if m:
            total = int(m.group(3).replace(",", ""))
            if total < self.tokens:
                return None  # Dashboard-Neuzeichnung; nie rückwärts zählen
            self.tokens = total
            if total >= self.stop_at:
                return f"token_budget_reached total={total} stop_at={self.stop_at}"
        return None

    def on_log(self, line: str) -> str | None:
        for rx in (DISPATCH, START_RUN):
            m = rx.search(line)
            if m:
                issue = m.group(1)
                if self.issue is None:
                    self.issue = issue
                elif issue != self.issue:
                    return f"second_issue issue={issue} first={self.issue}"
        m = DISPATCH.search(line)
        if m:
            self.dispatches += 1
            if self.dispatches > 1:
                return f"second_dispatch issue={m.group(1)}"
        if RETRY.search(line):
            return "retry_cycle_scheduled"
        if FINISHED.search(line):
            return "first_run_finished"
        m = SESSION.search(line)
        if m:
            self.sessions += 1
            if self.sessions > self.max_sessions:
                return f"loop_sessions sessions={self.sessions} max={self.max_sessions}"
        return None


def descendants(root: int) -> list[int]:
    children: dict[int, list[int]] = {}
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = (entry / "stat").read_text().rsplit(")", 1)[1].split()
            children.setdefault(int(fields[1]), []).append(int(entry.name))
        except (OSError, IndexError, ValueError):
            continue
    out, stack = [], [root]
    while stack:
        pid = stack.pop()
        for child in children.get(pid, []):
            out.append(child)
            stack.append(child)
    return out


def alive(pid: int) -> bool:
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        return state != "Z"
    except OSError:
        return False


def stop_tree(proc: subprocess.Popen, grace: float) -> bool:
    tree = [proc.pid, *descendants(proc.pid)]
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 5.0)):
        for pid in reversed(tree):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.time() + wait
        while time.time() < deadline:
            proc.poll()
            if not any(alive(p) for p in tree):
                break
            time.sleep(0.2)
        left = [p for p in tree if alive(p)]
        log("signal_sent", signal=sig.name, remaining=len(left))
        if not left:
            break
    proc.poll()
    left = [p for p in tree if alive(p)]
    return not left


def _log_files(path: Path) -> list[Path]:
    if path.is_dir():  # disk_log wrap: symphony.log.1, .2, ...
        return sorted(p for p in path.glob("symphony.log.*") if p.suffix[1:].isdigit())
    return [path]


def tail(path: Path, start_at_end: bool):
    pos: dict[Path, int] = {}
    if start_at_end:
        for f in _log_files(path):
            pos[f] = f.stat().st_size
    bufs: dict[Path, str] = {}
    while True:
        got = False
        for f in _log_files(path):
            if not f.exists():
                continue
            size = f.stat().st_size
            p = pos.get(f, 0)
            if size < p:
                p = 0  # rotiert/abgeschnitten
            if size > p:
                with f.open("r", encoding="utf-8", errors="replace") as fh:
                    fh.seek(p)
                    bufs[f] = bufs.get(f, "") + fh.read()
                    pos[f] = fh.tell()
                *lines, bufs[f] = bufs[f].split("\n")
                got = True
                yield from lines
            else:
                pos[f] = p
        if not got:
            yield None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--log", type=Path, required=True,
                    help="Symphony log file or log directory (all symphony.log.N)")
    ap.add_argument("--stdout-file", type=Path, required=True)
    ap.add_argument("--budget", type=int, default=2_000_000)
    ap.add_argument("--reserve", type=int, default=300_000)
    ap.add_argument("--max-sessions", type=int, default=3, help="agent.max_turns")
    ap.add_argument("--max-runtime", type=float, default=3600.0)
    ap.add_argument("--no-token-readout", type=float, default=300.0,
                    help="stop if no token line was seen for this many seconds")
    ap.add_argument("--grace", type=float, default=20.0)
    ap.add_argument("--poll", type=float, default=0.5)
    ap.add_argument("--log-from-start", action="store_true", help="tests only")
    ap.add_argument("command", nargs=argparse.REMAINDER)
    args = ap.parse_args(argv)
    cmd = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not cmd:
        ap.error("no command")
    rules = Rules(args.budget, args.reserve, args.max_sessions)
    args.stdout_file.parent.mkdir(parents=True, exist_ok=True)
    out = args.stdout_file.open("a", encoding="utf-8")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                            errors="replace", bufsize=1)
    log("started", pid=proc.pid, stop_at=rules.stop_at)
    reason: list[str] = []
    last_tokens_seen = [time.time()]

    def read_stdout() -> None:
        for line in proc.stdout:  # type: ignore[union-attr]
            out.write(line)
            out.flush()
            if TOKENS.search(ANSI.sub("", line)):
                last_tokens_seen[0] = time.time()
            r = rules.on_stdout(line)
            if r and not reason:
                reason.append(r)

    threading.Thread(target=read_stdout, daemon=True).start()
    started = time.time()
    log_lines = tail(args.log, start_at_end=not args.log_from_start)
    while not reason:
        if proc.poll() is not None:
            reason.append(f"child_exited code={proc.returncode}")
            break
        line = next(log_lines)
        if line is not None:
            r = rules.on_log(line)
            if r:
                reason.append(r)
            continue
        now = time.time()
        if now - started > args.max_runtime:
            reason.append("max_runtime")
        elif now - last_tokens_seen[0] > args.no_token_readout:
            reason.append("token_readout_missing")
        time.sleep(args.poll)
    log("stop", reason=reason[0], tokens=rules.tokens, issue=rules.issue,
        dispatches=rules.dispatches, sessions=rules.sessions)
    clean = stop_tree(proc, args.grace)
    log("terminated", clean=clean)
    out.close()
    if not clean:
        return 3
    return 0 if reason[0].startswith(("first_run_finished", "child_exited code=0")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
