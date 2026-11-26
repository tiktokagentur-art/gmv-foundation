"""Synthetic negative checks for the offline deployment-isolation policy."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deployment_policy import (  # noqa: E402
    REPOSITORY,
    Approval,
    ControlPlaneGrant,
    Deployment,
    ReleaseEvidence,
    ReleaseRequest,
    evaluate_release,
    main,
    validate_deployment_config,
    validate_railway_readback,
)

SHA = "a" * 40
OTHER_SHA = "b" * 40
DIGEST = "sha256:" + "1" * 64
OLD_DIGEST = "sha256:" + "2" * 64
POLICY_PATH = ROOT / "config" / "deployment-policy.json"
SYNTHETIC_IDS = {
    "staging": {
        "project": "synthetic-staging-project",
        "environment": "synthetic-staging-environment",
        "service": "synthetic-staging-service",
    },
    "production": {
        "project": "synthetic-production-project",
        "environment": "synthetic-production-environment",
        "service": "synthetic-production-service",
    },
}


class FakeAdapter:
    def __init__(self, evidence: ReleaseEvidence | None = None, *, unavailable: bool = False):
        self.evidence = evidence
        self.unavailable = unavailable
        self.calls = 0

    def read(self, release_request: ReleaseRequest) -> ReleaseEvidence:
        self.calls += 1
        if self.unavailable:
            raise ConnectionError("synthetic infrastructure failure")
        assert self.evidence is not None
        return self.evidence


@pytest.fixture
def config() -> dict:
    policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    for scope, identifiers in SYNTHETIC_IDS.items():
        for kind, ident in identifiers.items():
            policy[scope][f"{kind}_id_sha256"] = hashlib.sha256(ident.encode()).hexdigest()
    return policy


@pytest.fixture
def release_request() -> ReleaseRequest:
    return ReleaseRequest(
        repository=REPOSITORY,
        environment="production",
        event="workflow_dispatch",
        ref="refs/heads/main",
        actor="release-initiator",
        request_id="release-70-1",
        commit_sha=SHA,
        image_digest=DIGEST,
        rollback_deployment_id="previous-success",
        rollback_image_digest=OLD_DIGEST,
    )


@pytest.fixture
def evidence(config: dict) -> ReleaseEvidence:
    readback = {}
    for scope, identifiers in SYNTHETIC_IDS.items():
        expected = config[scope]
        readback[scope] = {
            **{f"{kind}_id": ident for kind, ident in identifiers.items()},
            **{
                key: expected[key]
                for key in (
                    "project",
                    "environment",
                    "service",
                    "source_repository",
                    "source_branch",
                    "auto_deploy",
                )
            },
        }
        if scope == "staging":
            readback[scope]["wait_for_ci"] = expected["wait_for_ci"]
    return ReleaseEvidence(
        main_sha=SHA,
        ci_sha=SHA,
        checks={"Lint and structure": "success", "Backend": "success", "Image": "success"},
        staging_image_digest=DIGEST,
        approval=Approval("github_protected_environment", "release-reviewer", SHA, True),
        control_plane_grant=ControlPlaneGrant("release-70-1", SHA, True),
        permissions=frozenset({"production_deploy"}),
        deployments=(),
        previous_deployment=Deployment("previous-success", OTHER_SHA, OLD_DIGEST, "SUCCESS"),
        rollback_schema_compatible=True,
        railway_readback=readback,
    )


def test_desired_policy_file_validates_offline(config: dict) -> None:
    assert validate_deployment_config(config) == ()
    assert validate_deployment_config(json.loads(POLICY_PATH.read_text(encoding="utf-8"))) == ()
    assert main(["--config", str(POLICY_PATH)]) == 0


def test_synthetic_complete_evidence_is_evaluable(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    # This is an algorithm sanity check, never evidence of a live authorization.
    decision = evaluate_release(release_request, FakeAdapter(evidence), config)
    assert decision.allowed is True


def test_pr_without_approval_cannot_reach_evidence_adapter(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    adapter = FakeAdapter(replace(evidence, approval=None))
    decision = evaluate_release(replace(release_request, event="pull_request"), adapter, config)
    assert decision.allowed is False
    assert "release_trigger_invalid" in decision.reasons
    assert adapter.calls == 0


@pytest.mark.parametrize("state", ["failure", "pending", None])
def test_failed_or_incomplete_ci_is_denied(
    state: str | None, release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    checks = dict(evidence.checks)
    if state is None:
        checks.pop("Backend")
    else:
        checks["Backend"] = state
    decision = evaluate_release(
        release_request, FakeAdapter(replace(evidence, checks=checks)), config
    )
    assert decision.allowed is False
    assert "required_ci_not_successful" in decision.reasons


def test_merge_without_release_authorization_is_denied(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    adapter = FakeAdapter(replace(evidence, approval=None))
    decision = evaluate_release(replace(release_request, event="push"), adapter, config)
    assert decision.allowed is False
    assert "release_trigger_invalid" in decision.reasons
    assert adapter.calls == 0
    decision = evaluate_release(release_request, adapter, config)
    assert decision.allowed is False
    assert "release_approval_invalid" in decision.reasons


def test_unintended_production_deploy_configuration_is_denied(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    config["production"]["auto_deploy"] = True
    config["production"]["source_branch"] = "main"
    adapter = FakeAdapter(evidence)
    decision = evaluate_release(release_request, adapter, config)
    assert decision.allowed is False
    assert "production_autodeploy_enabled_or_unknown" in decision.reasons
    assert "production_source_branch_set" in decision.reasons
    assert adapter.calls == 0


def test_mismatched_commit_sha_is_denied(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    decision = evaluate_release(
        replace(release_request, commit_sha=OTHER_SHA), FakeAdapter(evidence), config
    )
    assert decision.allowed is False
    assert "commit_sha_mismatch" in decision.reasons


@pytest.mark.parametrize("permissions", [frozenset(), frozenset({"read_only"})])
def test_missing_or_invalid_permission_is_denied(
    permissions: frozenset[str],
    release_request: ReleaseRequest,
    evidence: ReleaseEvidence,
    config: dict,
) -> None:
    decision = evaluate_release(
        release_request, FakeAdapter(replace(evidence, permissions=permissions)), config
    )
    assert decision.allowed is False
    assert "production_permission_missing" in decision.reasons


def test_truthy_string_approval_or_grant_is_denied(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    approval = replace(evidence.approval, approved="yes")
    grant = replace(evidence.control_plane_grant, active="yes")
    decision = evaluate_release(
        release_request,
        FakeAdapter(replace(evidence, approval=approval, control_plane_grant=grant)),
        config,
    )
    assert "release_approval_invalid" in decision.reasons
    assert "control_plane_grant_invalid" in decision.reasons


def test_duplicate_deployment_request_is_denied(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    existing = Deployment(
        "already-queued", OTHER_SHA, OLD_DIGEST, "QUEUED", release_request.request_id
    )
    decision = evaluate_release(
        release_request, FakeAdapter(replace(evidence, deployments=(existing,))), config
    )
    assert decision.allowed is False
    assert "duplicate_deployment" in decision.reasons


def test_same_artifact_already_deployed_is_denied(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    existing = Deployment("already-live", SHA, DIGEST, "SUCCESS", "earlier-release_request")
    decision = evaluate_release(
        release_request, FakeAdapter(replace(evidence, deployments=(existing,))), config
    )
    assert "duplicate_deployment" in decision.reasons


def test_missing_rollback_information_is_denied(
    release_request: ReleaseRequest, evidence: ReleaseEvidence, config: dict
) -> None:
    adapter = FakeAdapter(evidence)
    decision = evaluate_release(
        replace(release_request, rollback_deployment_id=""), adapter, config
    )
    assert decision.allowed is False
    assert "rollback_information_missing_or_invalid" in decision.reasons
    assert adapter.calls == 0
    decision = evaluate_release(
        release_request, FakeAdapter(replace(evidence, previous_deployment=None)), config
    )
    assert "rollback_not_ready" in decision.reasons
    decision = evaluate_release(
        release_request, FakeAdapter(replace(evidence, rollback_schema_compatible="yes")), config
    )
    assert "rollback_not_ready" in decision.reasons


def test_unreachable_infrastructure_fails_closed(
    release_request: ReleaseRequest, config: dict
) -> None:
    decision = evaluate_release(release_request, FakeAdapter(unavailable=True), config)
    assert decision.allowed is False
    assert decision.reasons == ("evidence_unavailable",)


def test_contradictory_deployment_configuration_is_denied(config: dict) -> None:
    broken = copy.deepcopy(config)
    broken["staging"]["wait_for_ci"] = False
    broken["production"].pop("auto_deploy")
    broken["production"]["source_branch"] = "main"
    errors = validate_deployment_config(broken)
    assert "staging_autodeploy_without_ci" in errors
    assert "production_autodeploy_enabled_or_unknown" in errors
    assert "production_source_branch_set" in errors


def test_missing_or_invalid_live_toggle_cannot_pass(config: dict) -> None:
    config["production"]["auto_deploy"] = "false"
    assert "production_autodeploy_enabled_or_unknown" in validate_deployment_config(config)
    config["production"]["auto_deploy"] = False
    config.pop("staging")
    assert "staging_missing" in validate_deployment_config(config)


def test_readback_requires_matching_scope_ids_and_explicit_toggles(
    config: dict, evidence: ReleaseEvidence
) -> None:
    readback = copy.deepcopy(evidence.railway_readback)
    readback["production"]["service_id"] = "synthetic-other-service"
    readback["production"].pop("auto_deploy")
    errors = validate_railway_readback(config, readback)
    assert "production_service_id_mismatch" in errors
    assert "production_auto_deploy_drift_or_unknown" in errors
    readback["staging"].pop("project_id")
    assert "staging_project_id_missing" in validate_railway_readback(config, readback)
