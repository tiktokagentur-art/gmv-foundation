"""Negative security tests for the GMV GitHub Moderator trust boundary."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from github_moderator_security import (  # noqa: E402
    APPLY_ENVIRONMENT,
    PRIVILEGED_ENVIRONMENT,
    allows_privileged_credentials,
    analyze_workflow_security,
    assert_no_token_leak,
    evaluate_apply_gate,
    refuse_privileged_use_from_pr_code,
    validate_workflow_file,
)
from github_moderator_validate import validate  # noqa: E402

PILOT = "tiktokagentur-art/gmv-foundation"
WORKFLOW = (ROOT / ".github/workflows/github-moderator.yml").read_text(
    encoding="utf-8"
)


def test_same_repo_pull_request_has_no_privileged_secrets() -> None:
    decision = allows_privileged_credentials(
        "pull_request",
        head_repo=PILOT,
        repository=PILOT,
    )
    assert decision.privileged_allowed is False
    assert decision.blocked is True
    assert "same-repository" in decision.reason
    assert "BLOCKED" in decision.reason


def test_fork_pull_request_has_no_privileged_secrets() -> None:
    decision = allows_privileged_credentials(
        "pull_request",
        head_repo="attacker/gmv-foundation",
        repository=PILOT,
    )
    assert decision.privileged_allowed is False
    assert decision.blocked is True
    assert "fork-or-external" in decision.reason


def test_pull_request_target_is_never_privileged() -> None:
    decision = allows_privileged_credentials(
        "pull_request_target",
        head_repo=PILOT,
        repository=PILOT,
    )
    assert decision.privileged_allowed is False
    assert decision.blocked is True


def test_privileged_paths_allow_app_credentials() -> None:
    for event in ("workflow_dispatch", "schedule", "push"):
        decision = allows_privileged_credentials(
            event,
            repository=PILOT,
            ref="refs/heads/main" if event == "push" else None,
        )
        assert decision.privileged_allowed is True, event


def test_push_to_non_main_is_not_privileged() -> None:
    decision = allows_privileged_credentials(
        "push",
        repository=PILOT,
        ref="refs/heads/feature/evil",
    )
    assert decision.privileged_allowed is False
    assert "BLOCKED" in decision.reason


def test_refuse_privileged_token_use_from_same_repo_pr_code() -> None:
    decision = refuse_privileged_use_from_pr_code(
        event_name="pull_request",
        attempting_action="create-github-app-token",
        head_repo=PILOT,
        repository=PILOT,
    )
    assert decision.blocked is True
    assert decision.privileged_allowed is False
    assert "create-github-app-token" in decision.reason


def test_refuse_privileged_token_use_from_fork_pr_code() -> None:
    decision = refuse_privileged_use_from_pr_code(
        event_name="pull_request",
        attempting_action="mint-installation-token",
        head_repo="evil/fork",
        repository=PILOT,
    )
    assert decision.blocked is True
    assert "mint-installation-token" in decision.reason


def test_apply_blocked_from_non_main_branch() -> None:
    decision = evaluate_apply_gate(
        event_name="workflow_dispatch",
        mode="APPLY",
        ref="refs/heads/cursor/evil-branch",
        apply_gate="enabled",
        environment_name=APPLY_ENVIRONMENT,
        environment_approved=True,
        has_app_credentials=True,
    )
    assert decision.allowed is False
    assert decision.status == "BLOCKED"
    assert any("refs/heads/main" in reason for reason in decision.reasons)


def test_apply_blocked_without_environment_approval() -> None:
    decision = evaluate_apply_gate(
        event_name="workflow_dispatch",
        mode="APPLY",
        ref="refs/heads/main",
        apply_gate="enabled",
        environment_name=APPLY_ENVIRONMENT,
        environment_approved=False,
        has_app_credentials=True,
    )
    assert decision.allowed is False
    assert decision.status == "BLOCKED"
    assert any("environment approval" in reason for reason in decision.reasons)


def test_apply_blocked_without_ceo_gate() -> None:
    decision = evaluate_apply_gate(
        event_name="workflow_dispatch",
        mode="APPLY",
        ref="refs/heads/main",
        apply_gate="",
        environment_name=APPLY_ENVIRONMENT,
        environment_approved=True,
        has_app_credentials=True,
    )
    assert decision.allowed is False
    assert decision.status == "BLOCKED"
    assert any("GMV_MODERATOR_APPLY_GATE" in reason for reason in decision.reasons)


def test_apply_blocked_with_wrong_environment_name() -> None:
    decision = evaluate_apply_gate(
        event_name="workflow_dispatch",
        mode="APPLY",
        ref="refs/heads/main",
        apply_gate="enabled",
        environment_name="unprotected",
        environment_approved=True,
        has_app_credentials=True,
    )
    assert decision.allowed is False
    assert any(APPLY_ENVIRONMENT in reason for reason in decision.reasons)


def test_apply_blocked_for_repo_outside_allowlist() -> None:
    decision = evaluate_apply_gate(
        event_name="workflow_dispatch",
        mode="APPLY",
        ref="refs/heads/main",
        apply_gate="enabled",
        environment_name=APPLY_ENVIRONMENT,
        environment_approved=True,
        has_app_credentials=True,
        repository="tiktokagentur-art/other-repo",
    )
    assert decision.allowed is False
    assert any("outside the allowlist" in reason for reason in decision.reasons)


def test_apply_blocked_without_app_credentials() -> None:
    decision = evaluate_apply_gate(
        event_name="workflow_dispatch",
        mode="APPLY",
        ref="refs/heads/main",
        apply_gate="enabled",
        environment_name=APPLY_ENVIRONMENT,
        environment_approved=True,
        has_app_credentials=False,
    )
    assert decision.allowed is False
    assert any("GitHub App credentials" in reason for reason in decision.reasons)


def test_apply_blocked_on_pull_request_event() -> None:
    decision = evaluate_apply_gate(
        event_name="pull_request",
        mode="APPLY",
        ref="refs/heads/main",
        apply_gate="enabled",
        environment_name=APPLY_ENVIRONMENT,
        environment_approved=True,
        has_app_credentials=True,
    )
    assert decision.allowed is False
    assert decision.status == "BLOCKED"


def test_apply_allowed_when_all_gates_pass() -> None:
    decision = evaluate_apply_gate(
        event_name="workflow_dispatch",
        mode="APPLY",
        ref="refs/heads/main",
        apply_gate="enabled",
        environment_name=APPLY_ENVIRONMENT,
        environment_approved=True,
        has_app_credentials=True,
        repository=PILOT,
    )
    assert decision.allowed is True
    assert decision.status == "ALLOWED"


def test_validate_rejects_missing_or_wrong_status_checks(tmp_path: Path) -> None:
    src = ROOT / "config" / "github"
    dest = tmp_path / "config" / "github"
    shutil.copytree(src, dest)
    # Keep a minimal workflow so validate_workflow_file does not fail first.
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    shutil.copy(
        ROOT / ".github/workflows/github-moderator.yml",
        workflow_dir / "github-moderator.yml",
    )
    ruleset_path = dest / "rulesets" / "main-branch-protection.json"
    payload = ruleset_path.read_text(encoding="utf-8")
    # Drop Backend check — wrong/incomplete status checks must fail closed.
    backend_snippet = (
        '{\n            "context": "Backend",\n'
        '            "integration_id": 15368\n'
        "          },\n          "
    )
    payload = payload.replace(backend_snippet, "")
    ruleset_path.write_text(payload, encoding="utf-8")
    errors = validate(tmp_path)
    assert any("missing required status check 'Backend'" in error for error in errors)


def test_validate_rejects_wrong_status_check_name(tmp_path: Path) -> None:
    src = ROOT / "config" / "github"
    dest = tmp_path / "config" / "github"
    shutil.copytree(src, dest)
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    shutil.copy(
        ROOT / ".github/workflows/github-moderator.yml",
        workflow_dir / "github-moderator.yml",
    )
    ruleset_path = dest / "rulesets" / "main-branch-protection.json"
    text = ruleset_path.read_text(encoding="utf-8").replace(
        "Lint and structure", "Lint and strutcture"
    )
    ruleset_path.write_text(text, encoding="utf-8")
    errors = validate(tmp_path)
    assert any(
        "missing required status check 'Lint and structure'" in error
        for error in errors
    )


def test_checked_in_workflow_passes_security_analysis() -> None:
    errors = validate_workflow_file(ROOT)
    assert errors == []
    assert "github.event_name != 'pull_request'" in WORKFLOW
    assert PRIVILEGED_ENVIRONMENT in WORKFLOW
    assert APPLY_ENVIRONMENT in WORKFLOW
    assert "\npull_request_target:" not in WORKFLOW
    assert "echo \"token=" not in WORKFLOW
    assert "trusted=true" not in WORKFLOW


def test_manipulated_workflow_with_pull_request_target_is_rejected() -> None:
    evil = WORKFLOW.replace("pull_request:", "pull_request_target:")
    errors = analyze_workflow_security(evil)
    assert any("pull_request_target is forbidden" in error for error in errors)


def test_manipulated_workflow_trusting_same_repo_pr_is_rejected() -> None:
    evil = (
        WORKFLOW
        + "\n# injected\n"
        + "REPO_TRUSTED=${{ github.event.pull_request.head.repo.full_name }}\n"
        + "trusted=true\n"
    )
    errors = analyze_workflow_security(evil)
    assert any("same-repository pull requests" in error for error in errors)


def test_manipulated_workflow_publishing_token_is_rejected() -> None:
    evil = WORKFLOW + '\n            echo "token=${APP_TOKEN}" >> "${GITHUB_OUTPUT}"\n'
    errors = analyze_workflow_security(evil)
    assert any("must not publish tokens" in error for error in errors)


def test_manipulated_workflow_without_event_gate_is_rejected() -> None:
    evil = WORKFLOW.replace("github.event_name != 'pull_request' && ", "")
    errors = analyze_workflow_security(evil)
    assert any("github.event_name != 'pull_request'" in error for error in errors)


def test_manipulated_workflow_without_privileged_environment_is_rejected() -> None:
    evil = WORKFLOW.replace(
        f"environment: {PRIVILEGED_ENVIRONMENT}",
        "environment: unprotected-temp",
    ).replace(PRIVILEGED_ENVIRONMENT, "unprotected-temp")
    errors = analyze_workflow_security(evil)
    assert any(PRIVILEGED_ENVIRONMENT in error for error in errors)


def test_token_leak_detector_blocks_private_key_material() -> None:
    # Build the marker at runtime so structure scanning does not treat this
    # fixture source as a checked-in secret.
    marker = "-----BEGIN " + "RSA PRIVATE " + "KEY-----"
    with pytest.raises(ValueError, match="BLOCKED"):
        assert_no_token_leak(marker + "\nAAAA")


def test_token_leak_detector_blocks_ghs_token() -> None:
    token = "ghs_" + "exampletokenvalue"
    with pytest.raises(ValueError, match="BLOCKED"):
        assert_no_token_leak(f"authorization: Bearer {token}")


def test_validation_and_unit_path_needs_no_privileged_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Config validation must succeed without App credentials in the environment."""
    for name in (
        "GMV_GITHUB_MODERATOR_APP_PRIVATE_KEY",
        "GMV_GITHUB_MODERATOR_APP_CLIENT_ID",
        "GITHUB_TOKEN",
        "GH_TOKEN",
    ):
        monkeypatch.delenv(name, raising=False)
    assert validate(ROOT) == []
    assert validate_workflow_file(ROOT) == []
