#!/usr/bin/env python3
"""Fail-closed, bounded manual Aline greeting. No credentials or side effects in preflight."""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request
from collections.abc import Mapping
from pathlib import Path

REPO = "tiktokagentur-art/gmv-foundation"
WORKFLOW = "aline-hello-once.yml"
MODEL = "gpt-6.1-terra"
QUESTION = "Hallo Aline! Wie geht es dir heute?"
ACTOR = "tiktokagentur-art"
ACTOR_ID = "354272348"
MAX_HISTORY_BYTES = 131072


class GateError(RuntimeError):
    """Deny API execution rather than weakening a missing gate."""


def validate_identity(env: Mapping[str, str]) -> None:
    required = {
        "GITHUB_REPOSITORY": REPO,
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "GITHUB_ACTOR": ACTOR,
        "GITHUB_ACTOR_ID": ACTOR_ID,
        "GITHUB_TRIGGERING_ACTOR": ACTOR,
    }
    for key, expected in required.items():
        if env.get(key) != expected:
            raise GateError(f"Denied: unexpected {key}")
    if not env.get("GITHUB_RUN_ID", "").isdecimal():
        raise GateError("Denied: missing valid GITHUB_RUN_ID")


# GitHub confirmed this particular dispatch failed before any runner or step.
# Only this precise failed attempt may be excluded when allowing a replacement run.
PRE_RUN_FAILURE_ID = 44694430741
PRE_RUN_FAILURE_SHA = "71557145872ca31862e1bd617bc6eeb01f7d5826"


def _read_github_json(url: str, token: str, opener) -> dict:
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with opener(request, timeout=12) as response:
            raw = response.read(MAX_HISTORY_BYTES + 1)
        if len(raw) > MAX_HISTORY_BYTES:
            raise GateError("Denied: oversized workflow-run history")
        data = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise GateError("Denied: GitHub workflow-run history unavailable") from exc
    if not isinstance(data, dict):
        raise GateError("Denied: unexpected GitHub response")
    return data


def _verify_prior_attempt_never_started(token: str, opener) -> None:
    """Do not assume 'failure' means no API request: require no runner and zero steps."""
    url = (
        f"https://api.github.com/repos/{REPO}/actions/runs/"
        f"{PRE_RUN_FAILURE_ID}/jobs?per_page=100"
    )
    payload = _read_github_json(url, token, opener)
    jobs = payload.get("jobs")
    if payload.get("total_count") != 1 or not isinstance(jobs, list) or len(jobs) != 1:
        raise GateError("Denied: prior attempt job evidence is incomplete")
    job = jobs[0]
    if (
        job.get("conclusion") != "failure"
        or job.get("status") != "completed"
        or job.get("runner_name") not in ("", None)
        or job.get("steps") != []
    ):
        raise GateError("Denied: prior attempt may have executed steps")


# Audit baseline: the two failed prior dispatches and the third waiting dispatch.
# A new policy does not change the code/SHA or result of those earlier runs.
BASELINE_RUNS = {
    44694430741: "71557145872ca31862e1bd617bc6eeb01f7d5826",
    44697167267: "eb96d7c714e5557e5c4caeef2e1870faf44c95a7",
    44705555401: "eb96d7c714e5557e5c4caeef2e1870faf44c95a7",
}
MAX_NEW_DISPATCHES = 5
MAX_TOTAL_DISPATCHES = len(BASELINE_RUNS) + MAX_NEW_DISPATCHES


def validate_bounded_dispatch(
    env: Mapping[str, str],
    token: str,
    opener=urllib.request.urlopen,
) -> None:
    """Permit at most five *new* manual tests after three attested historical runs.

    No reruns, no concurrent uncompleted predecessors, no unknown actors,
    no missing history, and no automatic model retries.
    """
    if not token:
        raise GateError("Denied: read-only GitHub Actions token missing")
    url = (
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/runs"
        "?event=workflow_dispatch&per_page=100"
    )
    payload = _read_github_json(url, token, opener)
    runs = payload.get("workflow_runs")
    count = payload.get("total_count")
    if (
        not isinstance(runs, list)
        or type(count) is not int
        or count != len(runs)
        or count < len(BASELINE_RUNS) + 1
        or count > MAX_TOTAL_DISPATCHES
    ):
        raise GateError("Denied: manual test count out of approved range")

    current_id = int(env["GITHUB_RUN_ID"])
    seen = set()
    found_current = False
    for run in runs:
        if not isinstance(run, dict):
            raise GateError("Denied: malformed workflow history")
        run_id = run.get("id")
        actor = run.get("actor")
        if (
            type(run_id) is not int
            or run_id in seen
            or run.get("event") != "workflow_dispatch"
            or run.get("head_branch") != "main"
            or run.get("run_attempt") != 1
            or not isinstance(actor, dict)
            or actor.get("login") != ACTOR
            or actor.get("id") != int(ACTOR_ID)
        ):
            raise GateError("Denied: untrusted workflow dispatch history")
        seen.add(run_id)
        if run_id in BASELINE_RUNS:
            if run.get("head_sha") != BASELINE_RUNS[run_id]:
                raise GateError("Denied: baseline commit changed")
            if run.get("status") != "completed":
                raise GateError("Denied: historic run still pending; cancel it first")
            expected = {"failure"} if run_id != 44705555401 else {"cancelled", "failure"}
            if run.get("conclusion") not in expected:
                raise GateError("Denied: unexpected historic run conclusion")
        else:
            if run_id <= max(BASELINE_RUNS):
                raise GateError("Denied: unknown historic workflow attempt")
            if run_id == current_id:
                found_current = True
            elif run.get("status") != "completed":
                raise GateError("Denied: earlier manual test still active")
    if not BASELINE_RUNS.keys() <= seen:
        raise GateError("Denied: missing original dispatch records")
    if not found_current or current_id != max(seen):
        raise GateError("Denied: this is not the latest approved manual dispatch")
    _verify_prior_attempt_never_started(token, opener)


# Only these public, documented error.code values may appear in workflow logs.
# In particular, never print provider response bodies, headers, messages, or keys.
SAFE_RATE_LIMIT_CODES = frozenset({
    "credit_balance_exhausted",
    "organization_usage_limit_exceeded",
    "organization_spend_limit_exceeded",
    "project_spend_limit_exceeded",
    "rate_limit_exceeded",
    "insufficient_quota",
})


def safe_rate_limit_code(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if code is None:
        body = getattr(exc, "body", None)
        if isinstance(body, dict):
            code = body.get("code")
    return code if isinstance(code, str) and code in SAFE_RATE_LIMIT_CODES else "unclassified"


async def ask_aline() -> str:
    """Reuse the reviewed Aline L1 instruction text with no tools or handoffs."""
    worker_dir = Path.cwd() / "worker-src" / "prototypes" / "aline-openai-worker"
    if not (worker_dir / "worker.py").is_file():
        raise GateError("Denied: pinned Aline worker missing")
    sys.path.insert(0, str(worker_dir))
    from worker import INSTRUCTIONS, WORKER_ID

    if WORKER_ID != "GMV-VE-001":
        raise GateError("Denied: unexpected worker identity")

    from agents import Agent, ModelSettings, RunConfig, Runner, set_default_openai_client
    from openai import AsyncOpenAI

    instructions = (
        INSTRUCTIONS
        + "\nSonderfall: ein kontrollierter, harmloser Grußtest ohne Ticket-Snapshot. "
        "Beantworte ausschließlich die kurze Frage auf Deutsch in einem Satz. "
        "Keine Aussagen über echte Arbeit, Verfügbarkeit, Freigaben oder Systemzugriffe."
    )
    agent = Agent(
        name="Aline (GMV-VE-001, L1 greeting test)",
        model=MODEL,
        instructions=instructions,
        tools=[],
        handoffs=[],
        model_settings=ModelSettings(max_tokens=128, store=False, timeout=40),
    )
    async with AsyncOpenAI(max_retries=0, timeout=45) as client:
        set_default_openai_client(client, use_for_tracing=False)
        result = await Runner.run(
            agent,
            QUESTION,
            max_turns=1,
            run_config=RunConfig(tracing_disabled=True),
        )
    reply = result.final_output
    if not isinstance(reply, str) or not reply.strip() or len(reply) > 800:
        raise GateError("Denied: no valid short Aline response")
    return " ".join(reply.split())


def main() -> int:
    try:
        validate_identity(os.environ)
        validate_bounded_dispatch(os.environ, os.getenv("GITHUB_TOKEN", ""))
        if len(sys.argv) == 2 and sys.argv[1] == "--preflight":
            print("ALINE-HELLO-001: identity and bounded manual history PASS; 0 API calls")
            return 0
        if len(sys.argv) != 1:
            raise GateError("Denied: unsupported arguments")
        if not os.getenv("OPENAI_API_KEY"):
            raise GateError("Denied: OPENAI_API_KEY missing")
        if os.getenv("OPENAI_MODEL") != MODEL:
            raise GateError("Denied: expected model not configured")
        reply = asyncio.run(ask_aline())
        print("ALINE-HELLO-001: API reply received; one turn, no tools or writes")
        print(f"Aline (GMV-VE-001): {reply}")
        return 0
    except GateError as exc:
        print(f"ALINE-HELLO-001 BLOCKED: {exc}", file=sys.stderr)
    except Exception as exc:
        # Sanitized provider error codes only. No response bodies or messages.
        if type(exc).__name__ == "RateLimitError":
            print(
                f"ALINE-HELLO-001 FAILED: RateLimitError/"
                f"{safe_rate_limit_code(exc)}",
                file=sys.stderr,
            )
        else:
            print(f"ALINE-HELLO-001 FAILED: {type(exc).__name__}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
