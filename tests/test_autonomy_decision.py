"""Negative/offline tests for GMV-AUTO-001; no network, tokens or merge calls."""

import json
from pathlib import Path

import pytest

from app.autonomy.decision import evaluate_readiness

CONFIG = Path(__file__).resolve().parents[1] / "config/autonomy/mandate-v1.json"
SHA = "a" * 40


def policy():
    return json.loads(CONFIG.read_text(encoding="utf-8"))


def evidence():
    return {
        "repository_full_name": "tiktokagentur-art/gmv-foundation",
        "target_branch": "main",
        "action": "merge",
        "risk": "R0",
        "protected_change": False,
        "head_sha": SHA,
        "ci_sha": SHA,
        "review_sha": SHA,
        "risk_sha": SHA,
        "checks": {"Lint and structure": "success", "Backend": "success", "Image": "success"},
        "author_id": "worker-1",
        "reviewer_id": "reviewer-2",
        "review_source": "github",
        "review_state": "APPROVED",
        "verified_reviewer_identity": True,
        "ruleset_required_approvals": 1,
        "ruleset_no_bypass": True,
        "strict_required_checks": True,
        "verified_workload_identity": True,
        "control_plane_lease_verified": True,
        "trusted_risk_classification": True,
        "deployment_separated": True,
        "production_source_isolated": True,
        "hard_limits_verified": True,
        "audit_sink_ready": True,
        "kill_switch_ready": True,
    }


def test_committed_policy_is_off_and_unprivileged():
    result = evaluate_readiness(policy(), evidence())
    assert result.readiness == "BLOCKED"
    assert "activation_disabled" in result.reasons
    assert not result.merge_authorized
    assert not result.deploy_authorized
    assert not result.permission_change_authorized


def test_hypothetical_clean_evidence_is_only_offline_candidate():
    config = policy()
    config["enabled"] = True  # test fixture; committed policy stays disabled
    result = evaluate_readiness(config, evidence())
    assert result.readiness == "CANDIDATE_ONLY"
    assert result.reasons == ()
    assert not result.merge_authorized and not result.deploy_authorized


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("repository_full_name", "other/repo", "repository_scope_mismatch"),
        ("target_branch", "unprotected", "target_branch_mismatch"),
        ("action", "deploy_production", "action_not_delegated"),
        ("action", "change_permissions", "action_not_delegated"),
        ("risk", "R2", "risk_not_eligible"),
        ("risk", "R4", "risk_not_eligible"),
        ("protected_change", True, "protected_change_or_unknown"),
        ("protected_change", None, "protected_change_or_unknown"),
        ("ci_sha", "b" * 40, "stale_ci"),
        ("review_sha", "b" * 40, "stale_review"),
        ("risk_sha", "b" * 40, "stale_risk_classification"),
        ("reviewer_id", "worker-1", "independent_formal_review_missing"),
        ("review_source", "synthetic", "independent_formal_review_missing"),
        ("review_state", "COMMENTED", "independent_formal_review_missing"),
        ("ruleset_required_approvals", 0, "ruleset_not_enforcing"),
        ("ruleset_no_bypass", False, "ruleset_not_enforcing"),
        ("control_plane_lease_verified", False, "control_plane_lease_verified_missing"),
        ("trusted_risk_classification", False, "trusted_risk_classification_missing"),
        ("deployment_separated", False, "deployment_separated_missing"),
        ("production_source_isolated", False, "production_source_isolated_missing"),
        ("hard_limits_verified", False, "hard_limits_verified_missing"),
        ("kill_switch_ready", False, "kill_switch_ready_missing"),
    ],
)
def test_fail_closed(field, value, reason):
    config = policy()
    config["enabled"] = True
    candidate = evidence()
    candidate[field] = value
    result = evaluate_readiness(config, candidate)
    assert result.readiness == "BLOCKED"
    assert reason in result.reasons
    assert not result.merge_authorized


def test_incomplete_input_never_authorizes():
    config = policy()
    config["enabled"] = True
    result = evaluate_readiness(config, {})
    assert result.readiness == "BLOCKED"
    assert not result.merge_authorized and not result.deploy_authorized


def test_staging_requires_immutable_artifact_and_rollback():
    config = policy()
    config["enabled"] = True
    candidate = evidence()
    candidate.update(action="deploy_staging", environment="staging")
    result = evaluate_readiness(config, candidate)
    assert "missing_immutable_artifact" in result.reasons
    assert "rollback_unavailable" in result.reasons
    candidate.update(
        artifact_commit_sha=SHA, artifact_digest="sha256:" + "b" * 64, rollback_ready=True
    )
    result = evaluate_readiness(config, candidate)
    assert result.readiness == "CANDIDATE_ONLY"
    assert not result.deploy_authorized


def test_boolean_is_not_an_approval_count():
    config = policy()
    config["enabled"] = True
    candidate = evidence()
    candidate["ruleset_required_approvals"] = True
    result = evaluate_readiness(config, candidate)
    assert "ruleset_not_enforcing" in result.reasons


def test_policy_scope_change_is_not_delegated():
    config = policy()
    config["enabled"] = True
    config["repository_full_name"] = "attacker/other"
    result = evaluate_readiness(config, evidence())
    assert "repository_scope_mismatch" in result.reasons
    assert not result.merge_authorized


def test_policy_target_change_is_not_delegated():
    config = policy()
    config["enabled"] = True
    config["target_branch"] = "other"
    result = evaluate_readiness(config, evidence())
    assert "target_branch_mismatch" in result.reasons
    assert not result.merge_authorized
