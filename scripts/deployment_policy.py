#!/usr/bin/env python3
"""Offline release policy for issue #70.

This module reads supplied evidence and returns a decision. It has no Railway
client, GitHub token, deployment command, or persistent release state. A future
executor must obtain evidence from trusted read-only adapters and keep the
server-side approval boundary outside untrusted pull-request code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

REPOSITORY = "tiktokagentur-art/gmv-foundation"
REQUIRED_CHECKS = ("Lint and structure", "Backend", "Image")
SHA_RE = re.compile(r"[0-9a-f]{40}\Z")
DIGEST_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
DEFAULT_CONFIG = Path(__file__).resolve().parents[1] / "config" / "deployment-policy.json"


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _valid_sha(value: object) -> bool:
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def _valid_digest(value: object) -> bool:
    return isinstance(value, str) and DIGEST_RE.fullmatch(value) is not None


@dataclass(frozen=True)
class ReleaseRequest:
    repository: str
    environment: str
    event: str
    ref: str
    actor: str
    request_id: str
    commit_sha: str
    image_digest: str
    rollback_deployment_id: str
    rollback_image_digest: str


@dataclass(frozen=True)
class Approval:
    source: str
    actor: str
    commit_sha: str
    approved: bool


@dataclass(frozen=True)
class ControlPlaneGrant:
    request_id: str
    commit_sha: str
    active: bool


@dataclass(frozen=True)
class Deployment:
    deployment_id: str
    commit_sha: str
    image_digest: str
    status: str
    request_id: str = ""


@dataclass(frozen=True)
class ReleaseEvidence:
    main_sha: str
    ci_sha: str
    checks: Mapping[str, str]
    staging_image_digest: str
    approval: Approval | None
    control_plane_grant: ControlPlaneGrant | None
    permissions: frozenset[str]
    deployments: tuple[Deployment, ...]
    previous_deployment: Deployment | None
    rollback_schema_compatible: bool
    railway_readback: Mapping[str, object] | None = None


class EvidenceAdapter(Protocol):
    """Read from existing authorities; never mint a release authorization."""

    def read(self, request: ReleaseRequest) -> ReleaseEvidence: ...


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reasons: tuple[str, ...]


def validate_deployment_config(config: object) -> tuple[str, ...]:
    """Validate a desired/read-back snapshot without claiming it is live state."""
    if not isinstance(config, dict):
        return ("config_invalid",)

    errors: list[str] = []
    if config.get("repository") != REPOSITORY:
        errors.append("repository_mismatch")

    staging = config.get("staging")
    production = config.get("production")
    fingerprints: list[str] = []
    if not isinstance(staging, dict):
        errors.append("staging_missing")
    else:
        for kind in ("project", "environment", "service"):
            fingerprint = staging.get(f"{kind}_id_sha256")
            if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
                errors.append(f"staging_{kind}_fingerprint_invalid")
            else:
                fingerprints.append(fingerprint)
        for key, expected in (
            ("project", "GMV-V3"),
            ("environment", "staging"),
            ("service", "backend"),
            ("source_repository", REPOSITORY),
            ("source_branch", "main"),
        ):
            if staging.get(key) != expected:
                errors.append(f"staging_{key}_mismatch")
        auto = staging.get("auto_deploy")
        wait = staging.get("wait_for_ci")
        if type(auto) is not bool:  # noqa: E721 - reject truthy strings from snapshots
            errors.append("staging_auto_deploy_invalid")
        if type(wait) is not bool:  # noqa: E721
            errors.append("staging_wait_for_ci_invalid")
        if auto is True and wait is not True:
            errors.append("staging_autodeploy_without_ci")

    if not isinstance(production, dict):
        errors.append("production_missing")
    else:
        for kind in ("project", "environment", "service"):
            fingerprint = production.get(f"{kind}_id_sha256")
            if not isinstance(fingerprint, str) or not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
                errors.append(f"production_{kind}_fingerprint_invalid")
            else:
                fingerprints.append(fingerprint)
        for key, expected in (
            ("project", "GMV Forge"),
            ("environment", "production"),
            ("service", "gmv-foundation"),
            ("release_mode", "approved_image"),
        ):
            if production.get(key) != expected:
                errors.append(f"production_{key}_mismatch")
        if "source_repository" not in production or production.get("source_repository") not in (
            None,
            REPOSITORY,
        ):
            errors.append("production_source_repository_invalid")
        if "source_branch" not in production:
            errors.append("production_source_branch_unknown")
        if production.get("source_branch") is not None:
            errors.append("production_source_branch_set")
        if production.get("auto_deploy") is not False:
            errors.append("production_autodeploy_enabled_or_unknown")
    if len(fingerprints) != len(set(fingerprints)):
        errors.append("scope_fingerprints_not_unique")
    return tuple(errors)


def validate_railway_readback(config: object, readback: object) -> tuple[str, ...]:
    """Compare a trusted Railway snapshot against the reviewed policy."""
    if validate_deployment_config(config):
        return ("policy_config_invalid",)
    if not isinstance(config, dict) or not isinstance(readback, dict):
        return ("railway_readback_unavailable",)

    errors: list[str] = []
    for scope in ("staging", "production"):
        expected = config[scope]
        actual = readback.get(scope)
        if not isinstance(actual, dict):
            errors.append(f"{scope}_readback_missing")
            continue
        for kind in ("project", "environment", "service"):
            ident = actual.get(f"{kind}_id")
            if not _nonempty(ident):
                errors.append(f"{scope}_{kind}_id_missing")
            elif hashlib.sha256(ident.encode("utf-8")).hexdigest() != expected[f"{kind}_id_sha256"]:
                errors.append(f"{scope}_{kind}_id_mismatch")
        for key in ("project", "environment", "service", "source_repository", "source_branch"):
            if key not in actual or actual[key] != expected[key]:
                errors.append(f"{scope}_{key}_drift")
        if actual.get("auto_deploy") is not expected["auto_deploy"]:
            errors.append(f"{scope}_auto_deploy_drift_or_unknown")
        if scope == "staging" and actual.get("wait_for_ci") is not expected["wait_for_ci"]:
            errors.append("staging_wait_for_ci_drift_or_unknown")
    return tuple(errors)


def evaluate_release(
    request: ReleaseRequest,
    adapter: EvidenceAdapter,
    config: object,
) -> Decision:
    """Fail closed on missing, mismatched, or unreachable release evidence."""
    reasons = list(validate_deployment_config(config))
    if request.repository != REPOSITORY:
        reasons.append("request_repository_mismatch")
    if request.environment != "production":
        reasons.append("request_environment_invalid")
    if request.event != "workflow_dispatch" or request.ref != "refs/heads/main":
        reasons.append("release_trigger_invalid")
    if not _nonempty(request.actor) or not _nonempty(request.request_id):
        reasons.append("request_identity_missing")
    if not _valid_sha(request.commit_sha):
        reasons.append("commit_sha_invalid")
    if not _valid_digest(request.image_digest):
        reasons.append("image_digest_invalid")
    if not _nonempty(request.rollback_deployment_id) or not _valid_digest(
        request.rollback_image_digest
    ):
        reasons.append("rollback_information_missing_or_invalid")

    # Do not contact an authority when the request or configuration is already
    # invalid. This also prevents a PR or push event from reaching privileged
    # adapters through this entry point.
    if reasons:
        return Decision(False, tuple(reasons))
    try:
        evidence = adapter.read(request)
    except Exception:
        return Decision(False, ("evidence_unavailable",))
    if not isinstance(evidence, ReleaseEvidence):
        return Decision(False, ("evidence_invalid",))
    if (
        not isinstance(evidence.checks, Mapping)
        or not isinstance(evidence.permissions, frozenset)
        or not isinstance(evidence.deployments, tuple)
        or any(not isinstance(item, Deployment) for item in evidence.deployments)
        or (evidence.approval is not None and not isinstance(evidence.approval, Approval))
        or (
            evidence.control_plane_grant is not None
            and not isinstance(evidence.control_plane_grant, ControlPlaneGrant)
        )
        or (
            evidence.previous_deployment is not None
            and not isinstance(evidence.previous_deployment, Deployment)
        )
    ):
        return Decision(False, ("evidence_invalid",))
    reasons.extend(validate_railway_readback(config, evidence.railway_readback))

    if evidence.main_sha != request.commit_sha or evidence.ci_sha != request.commit_sha:
        reasons.append("commit_sha_mismatch")
    if any(evidence.checks.get(name) != "success" for name in REQUIRED_CHECKS):
        reasons.append("required_ci_not_successful")
    if evidence.staging_image_digest != request.image_digest:
        reasons.append("staging_artifact_mismatch")

    approval = evidence.approval
    if (
        approval is None
        or approval.approved is not True
        or approval.source != "github_protected_environment"
        or approval.commit_sha != request.commit_sha
        or not _nonempty(approval.actor)
        or approval.actor == request.actor
    ):
        reasons.append("release_approval_invalid")
    grant = evidence.control_plane_grant
    if (
        grant is None
        or grant.active is not True
        or grant.request_id != request.request_id
        or grant.commit_sha != request.commit_sha
    ):
        reasons.append("control_plane_grant_invalid")
    if "production_deploy" not in evidence.permissions:
        reasons.append("production_permission_missing")

    if any(
        (
            deployment.request_id == request.request_id
            or (
                deployment.commit_sha == request.commit_sha
                and deployment.image_digest == request.image_digest
            )
        )
        and deployment.status not in {"FAILED", "REMOVED"}
        for deployment in evidence.deployments
    ):
        reasons.append("duplicate_deployment")
    previous = evidence.previous_deployment
    if (
        previous is None
        or previous.deployment_id != request.rollback_deployment_id
        or previous.image_digest != request.rollback_image_digest
        or previous.status != "SUCCESS"
        or evidence.rollback_schema_compatible is not True
    ):
        reasons.append("rollback_not_ready")

    return Decision(not reasons, tuple(reasons))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = parser.parse_args(argv)
    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("error: deployment policy file unavailable or invalid", file=sys.stderr)
        return 1
    errors = validate_deployment_config(config)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    print("deployment policy config ok (offline only)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
