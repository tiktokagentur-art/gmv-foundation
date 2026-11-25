#!/usr/bin/env python3
"""Fail-closed guard for the one-shot Aline API pilot. No OpenAI calls."""
import json
import os
import sys
import urllib.request

OWNER = "tiktokagentur-art"
REPO = "gmv-foundation"
WORKFLOW = "aline-start-001-once.yml"
ACK = "ALINE-START-001 EINMALIG FREIGEGEBEN"
ACTOR = "tiktokagentur-art"


class GateError(RuntimeError):
    """A model invocation must not proceed."""


def check_context(env):
    checks = {
        "GITHUB_REPOSITORY": f"{OWNER}/{REPO}",
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_ACTOR": ACTOR,
        "GITHUB_RUN_ATTEMPT": "1",
        "ALINE_AUTHORIZATION": ACK,
    }
    for key, expected in checks.items():
        if env.get(key) != expected:
            raise GateError(f"unsafe or missing {key}")
    run_id = env.get("GITHUB_RUN_ID", "")
    if not run_id.isdecimal() or int(run_id) < 1:
        raise GateError("missing positive GITHUB_RUN_ID")
    return int(run_id)


def check_history(history, run_id):
    """Any other workflow-dispatch run, even failed, makes this NO-GO."""
    if not isinstance(history, dict):
        raise GateError("history was not an object")
    runs = history.get("workflow_runs")
    if history.get("total_count") != 1 or not isinstance(runs, list) or len(runs) != 1:
        raise GateError("not exactly one recorded dispatch; previous/unclear attempt")
    run = runs[0]
    if not isinstance(run, dict) or run.get("id") != run_id:
        raise GateError("run identity mismatch")
    if (run.get("event") != "workflow_dispatch"
            or run.get("head_branch") != "main"
            or run.get("run_attempt") != 1):
        raise GateError("unexpected workflow run metadata")
    if run.get("actor", {}).get("login") != ACTOR:
        raise GateError("unexpected run actor")


def fetch_history(token):
    if not token:
        raise GateError("missing GITHUB_TOKEN; cannot inspect run history")
    url = (f"https://api.github.com/repos/{OWNER}/{REPO}"
           f"/actions/workflows/{WORKFLOW}/runs?event=workflow_dispatch&per_page=100")
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            data = response.read(512_001)
        if len(data) > 512_000:
            raise GateError("oversized history response")
        return json.loads(data)
    except GateError:
        raise
    except Exception:
        # Do not echo HTTP headers, request objects, token, or provider messages.
        raise GateError("GitHub history unavailable; fail closed") from None


def main():
    try:
        run_id = check_context(os.environ)
        check_history(fetch_history(os.environ.get("GITHUB_TOKEN", "")), run_id)
    except GateError as exc:
        print(f"NO-GO ALINE-START-001: {exc}", file=sys.stderr)
        return 1
    print("GO ALINE-START-001: single current dispatch, no earlier workflow runs")
    return 0


if __name__ == "__main__":
    sys.exit(main())
