"""Fail-closed, non-privileged readiness checks for GMV-AUTO-001.

This is deliberately NOT an authorization engine. Claims must be verified by
independent trusted integrations before any future runtime is built.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

_SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
_REQUIRED_CHECKS = ("Lint and structure", "Backend", "Image")
_ACTIONS = ("merge", "deploy_staging")


@dataclass(frozen=True)
class GateResult:
    readiness: str
    reasons: tuple[str, ...]
    merge_authorized: bool = False
    deploy_authorized: bool = False
    permission_change_authorized: bool = False


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and _SHA_RE.fullmatch(value) is not None


def evaluate_readiness(
    policy: Mapping[str, Any],
    evidence: Mapping[str, Any],
) -> GateResult:
    """Determine *offline candidacy*, never an operational authorization."""
    reasons: list[str] = []

    if policy.get("schema_version") != 1:
        reasons.append("unsupported_policy_version")
    if policy.get("enabled") is not True:
        reasons.append("activation_disabled")
    if policy.get("allowed_actions") != list(_ACTIONS):
        reasons.append("policy_action_scope_mismatch")

    # Only this specific repository and default branch are in the proposed mandate.
    # Claims are untrusted: these checks limit offline candidacy, not execution.
    if (
        policy.get("repository_full_name") != "tiktokagentur-art/gmv-foundation"
        or evidence.get("repository_full_name") != policy.get("repository_full_name")
    ):
        reasons.append("repository_scope_mismatch")
    if policy.get("target_branch") != "main" or evidence.get("target_branch") != "main":
        reasons.append("target_branch_mismatch")

    action = evidence.get("action")
    if action not in _ACTIONS:
        reasons.append("action_not_delegated")
    if evidence.get("risk") not in ("R0", "R1"):
        reasons.append("risk_not_eligible")
    if evidence.get("protected_change") is not False:
        reasons.append("protected_change_or_unknown")

    sha = evidence.get("head_sha")
    if not _valid_sha(sha):
        reasons.append("invalid_head_sha")
    if evidence.get("ci_sha") != sha or not _valid_sha(evidence.get("ci_sha")):
        reasons.append("stale_ci")
    if evidence.get("review_sha") != sha or not _valid_sha(evidence.get("review_sha")):
        reasons.append("stale_review")
    if evidence.get("risk_sha") != sha or not _valid_sha(evidence.get("risk_sha")):
        reasons.append("stale_risk_classification")

    checks = evidence.get("checks")
    if not isinstance(checks, dict) or any(
        checks.get(name) != "success" for name in _REQUIRED_CHECKS
    ):
        reasons.append("required_checks_missing")

    author = evidence.get("author_id")
    reviewer = evidence.get("reviewer_id")
    if (
        not isinstance(author, str)
        or not author
        or not isinstance(reviewer, str)
        or not reviewer
        or reviewer == author
        or evidence.get("review_source") != "github"
        or evidence.get("review_state") != "APPROVED"
        or evidence.get("verified_reviewer_identity") is not True
    ):
        reasons.append("independent_formal_review_missing")

    if (
        type(evidence.get("ruleset_required_approvals")) is not int
        or evidence["ruleset_required_approvals"] < 1
        or evidence.get("ruleset_no_bypass") is not True
        or evidence.get("strict_required_checks") is not True
    ):
        reasons.append("ruleset_not_enforcing")

    for name in (
        "verified_workload_identity",
        "control_plane_lease_verified",
        "trusted_risk_classification",
        "deployment_separated",
        "production_source_isolated",
        "hard_limits_verified",
        "audit_sink_ready",
        "kill_switch_ready",
    ):
        if evidence.get(name) is not True:
            reasons.append(name + "_missing")

    if action == "deploy_staging":
        if evidence.get("environment") != "staging":
            reasons.append("invalid_staging_environment")
        if evidence.get("artifact_commit_sha") != sha:
            reasons.append("stale_deploy_artifact")
        digest = evidence.get("artifact_digest")
        if not isinstance(digest, str) or _IMAGE_RE.fullmatch(digest) is None:
            reasons.append("missing_immutable_artifact")
        if evidence.get("rollback_ready") is not True:
            reasons.append("rollback_unavailable")

    # Never return EXECUTE/ALLOW: this module consumes illustrative claims only.
    return GateResult(
        readiness="CANDIDATE_ONLY" if not reasons else "BLOCKED",
        reasons=tuple(reasons),
    )
