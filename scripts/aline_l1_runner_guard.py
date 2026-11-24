#!/usr/bin/env python3
"""Fail-closed activation gate for the separate, repeatable Aline L1 runner.

This is NOT a provider-budget verifier. The platform owner must separately
verify the dedicated OpenAI project's *enforced* hard spend limit before
setting activation variables. See ADR-0015 and ALINE-L1-MANDATE.md.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path

REPOSITORY = "tiktokagentur-art/gmv-foundation"
MODEL = "gpt-6.1-terra"
MAX_FIXTURE_BYTES = 8192
MAX_CALCULATED_RUN_USD = 2.00
# Conservative preflight envelope. Real model overhead/usage must be checked
# separately; this estimate is NOT a provider-enforced per-request limit.
INPUT_TOKEN_ENVELOPE = 100_000
OUTPUT_TOKEN_CAP = 2_000
INPUT_USD_PER_M = 2.00
OUTPUT_USD_PER_M = 10.00


class GuardError(RuntimeError):
    """Explicit deny; never fall back to an unguarded API invocation."""


def conservative_estimate_usd() -> float:
    return (
        INPUT_TOKEN_ENVELOPE * INPUT_USD_PER_M
        + OUTPUT_TOKEN_CAP * OUTPUT_USD_PER_M
    ) / 1_000_000


def validate_environment(env: Mapping[str, str]) -> None:
    """Require a dedicated bot actor and one-time owner activation."""
    expected = {
        "GITHUB_EVENT_NAME": "workflow_dispatch",
        "GITHUB_REPOSITORY": REPOSITORY,
        "GITHUB_REF": "refs/heads/main",
        "GITHUB_RUN_ATTEMPT": "1",
        "ALINE_L1_ACTIVATED": "true",
        "ALINE_L1_PROJECT_DEDICATED": "true",
        "ALINE_L1_HARD_LIMIT_ATTESTED": "true",
        "ALINE_L1_BUDGET_USD": "10",
        "ALINE_L1_MODEL": MODEL,
    }
    for key, value in expected.items():
        if env.get(key, "") != value:
            raise GuardError(f"L1 denied: {key} does not match its gate")

    actor = env.get("ALINE_L1_ACTOR", "")
    if not actor or actor != env.get("GITHUB_ACTOR", ""):
        raise GuardError("L1 denied: actor not explicitly allowlisted")
    # Bind to immutable GitHub actor ID, not only a renamable account name.
    # Also require the triggering actor to match (defense in depth for re-runs).
    actor_id = env.get("GITHUB_ACTOR_ID", "")
    configured_id = env.get("ALINE_L1_ACTOR_ID", "")
    if not actor_id.isdecimal() or int(actor_id) <= 0 or actor_id != configured_id:
        raise GuardError("L1 denied: actor ID not attested")
    if actor == "tiktokagentur-art" or actor_id == "354272348":
        raise GuardError("L1 denied: shared human/admin account cannot be L1 bot")
    if env.get("GITHUB_TRIGGERING_ACTOR", "") != actor:
        raise GuardError("L1 denied: triggering actor differs from approved bot")

    if conservative_estimate_usd() > MAX_CALCULATED_RUN_USD:
        raise GuardError("L1 denied: conservative preflight cost exceeds 2 USD")


def validate_fixture(path: Path) -> None:
    if not path.is_file() or path.stat().st_size > MAX_FIXTURE_BYTES:
        raise GuardError("L1 denied: absent or oversized synthetic fixture")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as exc:
        raise GuardError("L1 denied: invalid synthetic fixture") from exc
    if data.get("synthetic") is not True:
        raise GuardError("L1 denied: non-synthetic fixture")
    ids = [item.get("ticket_id") for item in data.get("work_items", [])]
    if ids != ["EX-001", "EX-002"]:
        raise GuardError("L1 denied: unexpected synthetic ticket IDs")


def main() -> int:
    validate_environment(os.environ)
    fixture = os.environ.get("ALINE_L1_FIXTURE_PATH")
    if not fixture:
        raise GuardError("L1 denied: fixture path missing")
    validate_fixture(Path(fixture))
    print(
        json.dumps(
            {
                "guard": "PASS",
                "scope": "ALINE-L1-SYNTHETIC",
                "model": MODEL,
                "max_estimated_run_usd": MAX_CALCULATED_RUN_USD,
                "preflight_estimate_usd": round(conservative_estimate_usd(), 4),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
