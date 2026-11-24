#!/usr/bin/env python3
"""Dummy Symphony for watchdog tests: replays log/stdout lines, spawns a grandchild.

Args: LOGFILE STDOUT_SRC|- LOG_SRC|- IGNORE_SIGTERM(0/1) DELAY
"""
import signal
import subprocess
import sys
import time

logf, stdout_src, log_src, ignore_term, delay = (
    sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4] == "1", float(sys.argv[5]))
if ignore_term:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
child = subprocess.Popen(["sleep", "600"])  # Enkelprozess (wie codex app-server)
print(f"GRANDCHILD {child.pid}", file=sys.stderr, flush=True)
out = open(stdout_src, errors="replace") if stdout_src != "-" else iter(())  # noqa: SIM115
src = open(log_src, errors="replace") if log_src != "-" else iter(())  # noqa: SIM115
with open(logf, "a") as lf:
    for lline in src:
        lf.write(lline)
        lf.flush()
        sline = next(out, None)
        if sline is not None:
            sys.stdout.write(sline)
            sys.stdout.flush()
        time.sleep(delay)
    for sline in out:
        sys.stdout.write(sline)
        sys.stdout.flush()
        time.sleep(delay)
while True:
    print("│ Tokens: in 1 | out 0 | total 1", flush=True)
    time.sleep(0.5)
