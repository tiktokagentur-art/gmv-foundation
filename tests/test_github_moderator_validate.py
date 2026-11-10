"""Tests for GitHub Moderator configuration validation."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from github_moderator_validate import validate  # noqa: E402


def _seed_valid_tree(tmp_path: Path) -> Path:
    src = ROOT / "config" / "github"
    dest = tmp_path / "config" / "github"
    shutil.copytree(src, dest)
    workflow_dir = tmp_path / ".github" / "workflows"
    workflow_dir.mkdir(parents=True)
    shutil.copy(
        ROOT / ".github" / "workflows" / "github-moderator.yml",
        workflow_dir / "github-moderator.yml",
    )
    return tmp_path


def test_validate_accepts_pilot_config() -> None:
    errors = validate(ROOT)
    assert errors == []


def test_validate_rejects_extra_repository(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    repos = {
        "repos": [
            {"repo": "tiktokagentur-art/gmv-foundation"},
            {"repo": "tiktokagentur-art/other-repo"},
        ]
    }
    (root / "config/github/repos.yml").write_text(
        yaml.safe_dump(repos), encoding="utf-8"
    )
    errors = validate(root)
    assert any("pilot scope violation" in error for error in errors)


def test_validate_rejects_settings_outside_allowlist(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    settings = {
        "owner": "tiktokagentur-art",
        "rules": [
            {
                "selector": {"repos": ["tiktokagentur-art/not-allowed"]},
                "settings": {
                    "rulesets-file": [
                        "./config/github/rulesets/main-branch-protection.json"
                    ]
                },
            }
        ],
    }
    (root / "config/github/settings-config.yml").write_text(
        yaml.safe_dump(settings), encoding="utf-8"
    )
    errors = validate(root)
    assert any("not in repos.yml" in error for error in errors)


def test_validate_rejects_mandatory_reviews(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    ruleset_path = root / "config/github/rulesets/main-branch-protection.json"
    payload = json.loads(ruleset_path.read_text(encoding="utf-8"))
    for rule in payload["rules"]:
        if rule.get("type") == "pull_request":
            rule["parameters"]["required_approving_review_count"] = 1
    ruleset_path.write_text(json.dumps(payload), encoding="utf-8")
    errors = validate(root)
    assert any("required_approving_review_count must be 0" in error for error in errors)


def test_validate_rejects_missing_ci_check(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    ruleset_path = root / "config/github/rulesets/main-branch-protection.json"
    payload = json.loads(ruleset_path.read_text(encoding="utf-8"))
    for rule in payload["rules"]:
        if rule.get("type") == "required_status_checks":
            rule["parameters"]["required_status_checks"] = [
                {"context": "Lint and structure", "integration_id": 15368}
            ]
    ruleset_path.write_text(json.dumps(payload), encoding="utf-8")
    errors = validate(root)
    assert any("missing required status check 'Backend'" in error for error in errors)


def test_validate_rejects_all_selector(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    settings = {
        "owner": "tiktokagentur-art",
        "rules": [
            {
                "selector": {"all": True},
                "settings": {
                    "rulesets-file": [
                        "./config/github/rulesets/main-branch-protection.json"
                    ]
                },
            }
        ],
    }
    (root / "config/github/settings-config.yml").write_text(
        yaml.safe_dump(settings), encoding="utf-8"
    )
    errors = validate(root)
    assert any("all: true" in error for error in errors)


def test_validate_rejects_integration_bypass(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    ruleset_path = root / "config/github/rulesets/main-branch-protection.json"
    payload = json.loads(ruleset_path.read_text(encoding="utf-8"))
    payload["bypass_actors"] = [
        {
            "actor_id": 424242,
            "actor_type": "Integration",
            "bypass_mode": "always",
        }
    ]
    ruleset_path.write_text(json.dumps(payload), encoding="utf-8")
    errors = validate(root)
    assert any(
        "bypass_actors must be exactly []" in error and "Integration" in error
        for error in errors
    )


def test_validate_rejects_omitted_bypass_actors(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    ruleset_path = root / "config/github/rulesets/main-branch-protection.json"
    payload = json.loads(ruleset_path.read_text(encoding="utf-8"))
    del payload["bypass_actors"]
    ruleset_path.write_text(json.dumps(payload), encoding="utf-8")
    errors = validate(root)
    assert any("omitted is not an empty bypass list" in error for error in errors)


def test_validate_rejects_null_bypass_actors(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    ruleset_path = root / "config/github/rulesets/main-branch-protection.json"
    payload = json.loads(ruleset_path.read_text(encoding="utf-8"))
    payload["bypass_actors"] = None
    ruleset_path.write_text(json.dumps(payload), encoding="utf-8")
    errors = validate(root)
    assert any(
        "bypass_actors must be exactly []" in error and "got None" in error
        for error in errors
    )


def test_validate_rejects_invalid_json_ruleset(tmp_path: Path) -> None:
    root = _seed_valid_tree(tmp_path)
    ruleset_path = root / "config/github/rulesets/main-branch-protection.json"
    ruleset_path.write_text("{not-json", encoding="utf-8")
    errors = validate(root)
    assert any("invalid JSON" in error for error in errors)
