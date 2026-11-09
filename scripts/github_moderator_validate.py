#!/usr/bin/env python3
"""Validate GMV GitHub Moderator configuration before any API call."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import yaml  # noqa: E402
from github_moderator_lib import (  # noqa: E402
    GITHUB_ACTIONS_INTEGRATION_ID,
    PILOT_REPO,
    REPOS_PATH,
    REQUIRED_CHECK_CONTEXTS,
    ROOT,
    RULESETS_DIR,
    SETTINGS_PATH,
    allowlisted_repos,
    load_json,
    load_yaml,
    ruleset_paths_from_settings,
    settings_target_repos,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root (defaults to the workspace root)",
    )
    args = parser.parse_args(argv)
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        print(f"{len(errors)} github-moderator validation error(s)", file=sys.stderr)
        return 1
    print("github-moderator config ok")
    return 0


def validate(root: Path) -> list[str]:
    errors: list[str] = []
    repos_path = root / REPOS_PATH.relative_to(ROOT)
    settings_path = root / SETTINGS_PATH.relative_to(ROOT)
    rulesets_dir = root / RULESETS_DIR.relative_to(ROOT)

    if not repos_path.is_file():
        errors.append(f"missing {repos_path.relative_to(root)}")
        return errors
    if not settings_path.is_file():
        errors.append(f"missing {settings_path.relative_to(root)}")
        return errors

    try:
        repos_doc = load_yaml(repos_path)
        allowlist = allowlisted_repos(repos_doc)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"repos.yml: {exc}")
        return errors

    if not allowlist:
        errors.append("repos.yml allowlist is empty")
    for name in allowlist:
        if "/" not in name:
            errors.append(f"repos.yml entry must be owner/repo: {name!r}")
        if name != PILOT_REPO:
            errors.append(
                f"pilot scope violation: {name!r} is outside {PILOT_REPO!r}"
            )

    try:
        settings_doc = load_yaml(settings_path)
        targets = settings_target_repos(settings_doc)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        errors.append(f"settings-config.yml: {exc}")
        return errors

    allowset = set(allowlist)
    for target in targets:
        if target not in allowset:
            errors.append(
                f"settings-config.yml targets {target!r} which is not in repos.yml"
            )

    owner = settings_doc.get("owner")
    if owner != "tiktokagentur-art":
        errors.append(
            f"settings-config.yml owner must be 'tiktokagentur-art' during the pilot "
            f"(got {owner!r})"
        )

    try:
        ruleset_paths = ruleset_paths_from_settings(settings_doc, root=root)
    except ValueError as exc:
        errors.append(f"settings-config.yml: {exc}")
        return errors

    if not ruleset_paths:
        errors.append("settings-config.yml must reference at least one ruleset file")

    seen_names: set[str] = set()
    for path in ruleset_paths:
        try:
            rel: Path | str = path.relative_to(root)
        except ValueError:
            rel = path
        if not path.is_file():
            errors.append(f"ruleset file missing: {rel}")
            continue
        if rulesets_dir not in path.parents and path.parent != rulesets_dir:
            errors.append(f"ruleset file must live under config/github/rulesets/: {rel}")
        try:
            payload = load_json(path)
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"{rel}: invalid JSON ({exc})")
            continue
        errors.extend(_validate_ruleset(payload, Path(rel).as_posix()))
        name = payload.get("name")
        if isinstance(name, str):
            if name in seen_names:
                errors.append(f"duplicate ruleset name {name!r}")
            seen_names.add(name)
    return errors


def _validate_ruleset(payload: object, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return [f"{label}: ruleset root must be a JSON object"]
    for field in ("name", "target", "enforcement", "conditions", "rules"):
        if field not in payload:
            errors.append(f"{label}: missing field {field!r}")
    if payload.get("target") != "branch":
        errors.append(f"{label}: target must be 'branch' for the pilot")
    if payload.get("enforcement") != "active":
        errors.append(f"{label}: enforcement must be 'active'")
    if payload.get("name") != "main":
        errors.append(f"{label}: pilot ruleset name must be 'main' (updates existing)")

    conditions = payload.get("conditions")
    if isinstance(conditions, dict):
        include = (conditions.get("ref_name") or {}).get("include")
        if include != ["~DEFAULT_BRANCH"]:
            errors.append(
                f"{label}: conditions.ref_name.include must be ['~DEFAULT_BRANCH']"
            )

    rules = payload.get("rules")
    if not isinstance(rules, list):
        errors.append(f"{label}: rules must be a list")
        return errors

    types = [rule.get("type") for rule in rules if isinstance(rule, dict)]
    for required in ("deletion", "non_fast_forward", "pull_request", "required_status_checks"):
        if required not in types:
            errors.append(f"{label}: missing required rule type {required!r}")

    for rule in rules:
        if not isinstance(rule, dict):
            errors.append(f"{label}: each rule must be an object")
            continue
        if rule.get("type") == "pull_request":
            params = rule.get("parameters") or {}
            count = params.get("required_approving_review_count")
            if count != 0:
                errors.append(
                    f"{label}: required_approving_review_count must be 0 "
                    f"(CEO decision: no mandatory reviews); got {count!r}"
                )
            if params.get("require_code_owner_review") is True:
                errors.append(
                    f"{label}: require_code_owner_review must stay false during the pilot"
                )
        if rule.get("type") == "required_status_checks":
            params = rule.get("parameters") or {}
            checks = params.get("required_status_checks") or []
            contexts = {
                item.get("context")
                for item in checks
                if isinstance(item, dict)
            }
            for context in REQUIRED_CHECK_CONTEXTS:
                if context not in contexts:
                    errors.append(f"{label}: missing required status check {context!r}")
            for item in checks:
                if not isinstance(item, dict):
                    continue
                if item.get("integration_id") != GITHUB_ACTIONS_INTEGRATION_ID:
                    errors.append(
                        f"{label}: status check {item.get('context')!r} must use "
                        f"integration_id {GITHUB_ACTIONS_INTEGRATION_ID} (GitHub Actions)"
                    )
            if params.get("strict_required_status_checks_policy") is not True:
                errors.append(
                    f"{label}: strict_required_status_checks_policy must be true"
                )
    return errors


if __name__ == "__main__":
    raise SystemExit(main())
