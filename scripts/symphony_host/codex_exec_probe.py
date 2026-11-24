#!/usr/bin/env python3
"""Run one probe command through `codex app-server` command/exec (no model call).

Uses codex.command and codex.turn_sandbox_policy from the given WORKFLOW file,
exactly as Symphony@be10a1b sends them. Prints only the probe's stdout.
"""

from __future__ import annotations

import json
import subprocess
import sys

import yaml

PROBE_NET = (
    'for u in https://github.com/ https://api.github.com/zen https://api.openai.com/v1/models '
    "https://example.com/ https://pypi.org/simple/; do "
    'echo "NET $u -> $(timeout 10 curl -s -o /dev/null -w %{http_code} "$u")"; done'
)
PROBE_WRITE = (
    'w(){ (echo x > "$1") 2>/dev/null && echo "WRITE erlaubt: $1" '
    '|| echo "WRITE verweigert: $1"; }; '
    "w ./probe.txt; w ../SELFTEST-B/probe.txt; w /tmp/probe.txt; "
    'w "$HOME/probe.txt"; rm -f ./probe.txt'
)


def main() -> int:
    workflow, cwd, probe_paths = sys.argv[1], sys.argv[2], sys.argv[3]
    text = open(workflow, encoding="utf-8").read()
    front = text[4 : text.index("\n---\n", 4)]
    codex = yaml.safe_load(front)["codex"]
    proc = subprocess.Popen(
        ["bash", "-lc", "exec " + codex["command"]],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        text=True, cwd=cwd,
    )

    def send(msg: dict) -> None:
        proc.stdin.write(json.dumps(msg) + "\n")
        proc.stdin.flush()

    def wait(msg_id: int) -> dict:
        for line in proc.stdout:
            msg = json.loads(line)
            if msg.get("id") == msg_id:
                return msg
        raise SystemExit("app-server ended")

    try:
        send({"method": "initialize", "id": 1,
              "params": {"clientInfo": {"name": "gmv-sandbox-selftest", "version": "1"}}})
        wait(1)
        send({"method": "initialized", "params": {}})
        script = "; ".join([probe_paths, PROBE_WRITE, PROBE_NET])
        send({"method": "command/exec", "id": 2, "params": {
            "command": ["bash", "-c", script], "cwd": cwd, "timeoutMs": 120000,
            "sandboxPolicy": codex["turn_sandbox_policy"]}})
        res = wait(2)
        body = res.get("result") or {}
        if "error" in res:
            print("command/exec error:", res["error"].get("message"))
            return 1
        print(body.get("stdout", ""), end="")
        return 0
    finally:
        proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
