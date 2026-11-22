"""RFL-001: deterministic, offline review-fix planner with NO execution rights.

This module does not use GitHub, Codex, model APIs, credentials or a scheduler.
All inputs are untrusted. It only emits a candidate next step for an
independently authenticated GMVGANG Control Plane to consider in the future.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

REQUIRED_CHECKS = frozenset({"Lint and structure", "Backend", "Image"})
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
MAX_FIX_ATTEMPTS = 2
MAX_CHANGED_FILES = 5


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ChangedFile(StrictModel):
    path: str = Field(min_length=1)
    status: Literal["added", "modified", "removed", "renamed"]


class Finding(StrictModel):
    priority: Literal["P0", "P1", "P2", "P3"]
    path: str = Field(min_length=1)


class LoopSnapshot(StrictModel):
    schema_version: Literal[1]
    repository: Literal["tiktokagentur-art/gmv-foundation"]
    pr_number: int = Field(gt=0)
    pr_state: Literal["open", "closed"]
    draft: bool = Field(strict=True)
    head_sha: str
    review_head_sha: str
    checks_head_sha: str
    author_id: str = Field(min_length=1)
    reviewer_id: str = Field(min_length=1)
    review_source: Literal["codex_review"]
    review_completed: bool = Field(strict=True)
    review_state: Literal["COMMENTED", "APPROVED", "CHANGES_REQUESTED", "DISMISSED"]
    risk_class: Literal["R0", "R1", "R2", "R3", "R4"]
    changed_files: tuple[ChangedFile, ...] = Field(min_length=1)
    findings: tuple[Finding, ...]
    passed_checks: frozenset[str]
    approved_paths: frozenset[str]
    category_approved: bool = Field(strict=True)
    fix_attempts: int = Field(ge=0, strict=True)
    spend_limit_cents: int = Field(ge=0, strict=True)
    spent_cents: int = Field(ge=0, strict=True)
    estimated_next_fix_cents: int = Field(ge=0, strict=True)


class LoopDecision(StrictModel):
    schema_version: Literal[1] = 1
    next_action: Literal["BLOCKED", "PROPOSE_FIX_ONLY", "REQUEST_FINAL_REVIEW"]
    reasons: tuple[str, ...]
    remaining_attempts: int
    estimated_remaining_budget_cents: int
    write_authorized: Literal[False] = False
    merge_authorized: Literal[False] = False
    deploy_authorized: Literal[False] = False


def _eligible_path(path: str, risk: str) -> bool:
    """Conservative scope subset of APR-005A; NOT a replacement risk classifier."""
    if (
        path.startswith("/")
        or "\\" in path
        or "//" in path
        or any(ord(ch) < 32 for ch in path)
        or any(part in (".", "..", "") for part in path.split("/"))
        or PurePosixPath(path).as_posix() != path
    ):
        return False
    if risk == "R0":
        return path.startswith(("docs/guides/", "docs/tutorials/")) and path.endswith(".md")
    if risk == "R1":
        return path.startswith(("tests/fixtures/", "tests/mocks/")) and path.endswith(
            (".json", ".py", ".yaml")
        )
    return False


def evaluate(snapshot: LoopSnapshot) -> LoopDecision:
    """Advisory classification only; never dispatch a fix or authorize a merge."""
    reasons: list[str] = []
    paths = {change.path for change in snapshot.changed_files}

    if snapshot.pr_state != "open" or not snapshot.draft:
        reasons.append("pilot_requires_open_draft_pr")
    if any(not SHA_RE.fullmatch(sha) for sha in (
        snapshot.head_sha, snapshot.review_head_sha, snapshot.checks_head_sha
    )):
        reasons.append("invalid_sha")
    if snapshot.review_head_sha != snapshot.head_sha:
        reasons.append("stale_review")
    if snapshot.checks_head_sha != snapshot.head_sha:
        reasons.append("stale_ci")
    if snapshot.reviewer_id == snapshot.author_id:
        reasons.append("self_review")
    if not snapshot.review_completed or snapshot.review_state not in ("COMMENTED", "APPROVED"):
        reasons.append("review_not_completed")
    if not REQUIRED_CHECKS.issubset(snapshot.passed_checks):
        reasons.append("required_checks_missing")
    if snapshot.risk_class not in ("R0", "R1"):
        reasons.append("risk_requires_manual_review")
    if not snapshot.category_approved:
        reasons.append("category_not_approved")
    if len(snapshot.changed_files) > MAX_CHANGED_FILES or len(paths) != len(
        snapshot.changed_files
    ):
        reasons.append("invalid_change_scope")
    if not paths.issubset(snapshot.approved_paths):
        reasons.append("unapproved_paths")
    if any(
        change.status not in ("added", "modified")
        or not _eligible_path(change.path, snapshot.risk_class)
        for change in snapshot.changed_files
    ):
        reasons.append("unsafe_change_scope")
    if any(f.path not in paths for f in snapshot.findings):
        reasons.append("finding_outside_change_scope")
    if any(f.priority in ("P0", "P1") for f in snapshot.findings):
        reasons.append("high_priority_finding_requires_manual_review")
    if snapshot.fix_attempts >= MAX_FIX_ATTEMPTS:
        reasons.append("fix_attempt_limit_reached")
    if snapshot.spend_limit_cents == 0 or snapshot.estimated_next_fix_cents == 0:
        reasons.append("hard_budget_not_configured")
    if (
        snapshot.spent_cents + snapshot.estimated_next_fix_cents
        > snapshot.spend_limit_cents
    ):
        reasons.append("hard_budget_exceeded")

    action = "BLOCKED"
    if not reasons:
        action = "PROPOSE_FIX_ONLY" if snapshot.findings else "REQUEST_FINAL_REVIEW"

    return LoopDecision(
        next_action=action,
        reasons=tuple(reasons),
        remaining_attempts=max(0, MAX_FIX_ATTEMPTS - snapshot.fix_attempts),
        estimated_remaining_budget_cents=max(
            0, snapshot.spend_limit_cents - snapshot.spent_cents
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot", type=Path, help="offline untrusted JSON fixture")
    args = parser.parse_args()
    try:
        data = json.loads(args.snapshot.read_text(encoding="utf-8"))
        result = evaluate(LoopSnapshot.model_validate(data))
    except (ValueError, OSError, ValidationError):
        print(json.dumps({
            "next_action": "BLOCKED",
            "reasons": ["invalid_input"],
            "write_authorized": False,
            "merge_authorized": False,
            "deploy_authorized": False,
        }))
        return 2
    print(result.model_dump_json())
    # A positive advisory proposal is NOT an executable or formal CI approval.
    return 0 if result.next_action != "BLOCKED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
