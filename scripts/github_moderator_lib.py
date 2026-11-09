"""Shared helpers for the GMV GitHub Moderator configuration tooling."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPOS_PATH = ROOT / "config" / "github" / "repos.yml"
SETTINGS_PATH = ROOT / "config" / "github" / "settings-config.yml"
RULESETS_DIR = ROOT / "config" / "github" / "rulesets"

PILOT_REPO = "tiktokagentur-art/gmv-foundation"
REQUIRED_CHECK_CONTEXTS = ("Lint and structure", "Backend", "Image")
GITHUB_ACTIONS_INTEGRATION_ID = 15368


def load_yaml(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def allowlisted_repos(repos_doc: dict[str, Any] | None = None) -> list[str]:
    doc = repos_doc if repos_doc is not None else load_yaml(REPOS_PATH)
    if not isinstance(doc, dict) or "repos" not in doc:
        raise ValueError("repos.yml must contain a top-level 'repos' list")
    names: list[str] = []
    for entry in doc["repos"]:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict) and "repo" in entry:
            names.append(str(entry["repo"]))
        else:
            raise ValueError(f"invalid repos.yml entry: {entry!r}")
    return names


def settings_target_repos(settings_doc: dict[str, Any] | None = None) -> list[str]:
    doc = settings_doc if settings_doc is not None else load_yaml(SETTINGS_PATH)
    if not isinstance(doc, dict) or "rules" not in doc:
        raise ValueError("settings-config.yml must contain a top-level 'rules' list")
    targets: list[str] = []
    for index, rule in enumerate(doc["rules"]):
        if not isinstance(rule, dict):
            raise ValueError(f"rule {index} must be a mapping")
        selector = rule.get("selector") or {}
        if not isinstance(selector, dict):
            raise ValueError(f"rule {index} selector must be a mapping")
        if selector.get("all") is True:
            raise ValueError(
                f"rule {index}: selector 'all: true' is forbidden in the pilot"
            )
        if "custom-property" in selector:
            raise ValueError(
                f"rule {index}: custom-property selectors are forbidden in the pilot"
            )
        repos = selector.get("repos")
        if not repos:
            raise ValueError(f"rule {index}: selector.repos is required")
        if not isinstance(repos, list):
            raise ValueError(f"rule {index}: selector.repos must be a list")
        targets.extend(str(name) for name in repos)
    return targets


def ruleset_paths_from_settings(
    settings_doc: dict[str, Any] | None = None,
    *,
    root: Path | None = None,
) -> list[Path]:
    doc = settings_doc if settings_doc is not None else load_yaml(SETTINGS_PATH)
    base = root if root is not None else ROOT
    paths: list[Path] = []
    for index, rule in enumerate(doc["rules"]):
        settings = rule.get("settings") or {}
        raw = settings.get("rulesets-file")
        if raw is None:
            continue
        if isinstance(raw, str):
            items = [part.strip() for part in raw.replace("\n", ",").split(",") if part.strip()]
        elif isinstance(raw, list):
            items = [str(item) for item in raw]
        else:
            raise ValueError(f"rule {index}: rulesets-file must be a string or list")
        for item in items:
            path = Path(item)
            if not path.is_absolute():
                path = (base / item).resolve()
            paths.append(path)
    return paths


def normalize_ruleset_for_compare(ruleset: dict[str, Any]) -> dict[str, Any]:
    """Drop read-only API fields so desired and actual rulesets can be compared."""
    drop = {
        "id",
        "node_id",
        "source",
        "source_type",
        "_links",
        "created_at",
        "updated_at",
        "current_user_can_bypass",
    }
    cleaned = {key: value for key, value in ruleset.items() if key not in drop}
    rules = cleaned.get("rules")
    if isinstance(rules, list):
        cleaned["rules"] = [_normalize_rule(rule) for rule in rules]
    return cleaned


def _normalize_rule(rule: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(rule, dict):
        return rule
    out = dict(rule)
    params = out.get("parameters")
    if not isinstance(params, dict):
        return out
    params = dict(params)
    checks = params.get("required_status_checks")
    if isinstance(checks, list):
        params["required_status_checks"] = sorted(
            [
                {
                    "context": item.get("context"),
                    "integration_id": item.get("integration_id"),
                }
                for item in checks
                if isinstance(item, dict)
            ],
            key=lambda item: (item.get("context") or "", item.get("integration_id") or 0),
        )
    methods = params.get("allowed_merge_methods")
    if isinstance(methods, list):
        params["allowed_merge_methods"] = sorted(methods)
    # GitHub always returns required_reviewers on read; treat omission as [].
    if "required_reviewers" not in params:
        params["required_reviewers"] = []
    out["parameters"] = params
    return out


def compare_rulesets(
    desired: dict[str, Any], actual: dict[str, Any] | None
) -> list[str]:
    """Return human-readable differences between desired and actual rulesets."""
    diffs: list[str] = []
    if actual is None:
        diffs.append(f"ruleset {desired.get('name')!r} is missing on the repository")
        return diffs

    left = normalize_ruleset_for_compare(desired)
    right = normalize_ruleset_for_compare(actual)

    for field in ("name", "target", "enforcement"):
        if left.get(field) != right.get(field):
            diffs.append(f"{field}: actual={right.get(field)!r} desired={left.get(field)!r}")

    left_conditions = left.get("conditions")
    right_conditions = right.get("conditions")
    if left_conditions != right_conditions:
        diffs.append("conditions differ")

    left_rules = {rule.get("type"): rule for rule in left.get("rules", [])}
    right_rules = {rule.get("type"): rule for rule in right.get("rules", [])}

    for rule_type in sorted(set(left_rules) | set(right_rules)):
        if rule_type not in right_rules:
            diffs.append(f"rule missing on repository: {rule_type}")
            continue
        if rule_type not in left_rules:
            diffs.append(f"extra rule on repository (not in desired config): {rule_type}")
            continue
        if left_rules[rule_type] != right_rules[rule_type]:
            diffs.append(f"rule differs: {rule_type}")
            if rule_type == "required_status_checks":
                left_checks = (
                    left_rules[rule_type].get("parameters", {}).get("required_status_checks", [])
                )
                right_checks = (
                    right_rules[rule_type]
                    .get("parameters", {})
                    .get("required_status_checks", [])
                )
                diffs.append(f"  desired checks: {left_checks}")
                diffs.append(f"  actual checks:  {right_checks}")
            if rule_type == "pull_request":
                diffs.append(
                    "  desired pull_request parameters: "
                    f"{left_rules[rule_type].get('parameters')}"
                )
                diffs.append(
                    "  actual pull_request parameters:  "
                    f"{right_rules[rule_type].get('parameters')}"
                )
    return diffs
