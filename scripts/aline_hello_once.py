#!/usr/bin/env python3
"""Fail-closed, single-use Aline greeting. No credentials or side effects in preflight."""

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


def validate_first_dispatch(
    env: Mapping[str, str],
    token: str,
    opener=urllib.request.urlopen,
) -> None:
    """Require that this workflow has exactly one dispatch run: the current run."""
    if not token:
        raise GateError("Denied: read-only GitHub Actions token missing")
    url = (
        f"https://api.github.com/repos/{REPO}/actions/workflows/{WORKFLOW}/runs"
        "?event=workflow_dispatch&per_page=100"
    )
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
        payload = json.loads(raw)
    except (OSError, ValueError) as exc:
        raise GateError("Denied: GitHub workflow-run history unavailable") from exc
    runs = payload.get("workflow_runs")
    if (
        payload.get("total_count") != 1
        or not isinstance(runs, list)
        or len(runs) != 1
        or str(runs[0].get("id")) != env["GITHUB_RUN_ID"]
    ):
        raise GateError("Denied: this is not the only dispatch run")


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
        + "\nSonderfall: ein einmaliger, harmloser Grußtest ohne Ticket-Snapshot. "
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
        validate_first_dispatch(os.environ, os.getenv("GITHUB_TOKEN", ""))
        if len(sys.argv) == 2 and sys.argv[1] == "--preflight":
            print("ALINE-HELLO-001: identity and one-shot history PASS; 0 API calls")
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
        # Do not leak provider error bodies, credentials, headers or responses.
        print(f"ALINE-HELLO-001 FAILED: {type(exc).__name__}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
