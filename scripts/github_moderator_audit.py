#!/usr/bin/env python3
"""Audit and readback helper for the GMV GitHub Moderator.

Reads live repository rulesets via the GitHub API and compares them to the
desired configuration under config/github/. Never writes repository settings.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from github_moderator_lib import (  # noqa: E402
    PILOT_REPO,
    ROOT,
    allowlisted_repos,
    compare_rulesets,
    load_json,
    load_yaml,
    ruleset_paths_from_settings,
)
from github_moderator_validate import validate  # noqa: E402

API_VERSION = "2022-11-28"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--repo",
        default=PILOT_REPO,
        help="owner/repo to audit (must be allowlisted)",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or "",
        help="GitHub token (defaults to GITHUB_TOKEN / GH_TOKEN)",
    )
    parser.add_argument(
        "--api-url",
        default=os.environ.get("GITHUB_API_URL", "https://api.github.com"),
    )
    parser.add_argument(
        "--report",
        type=Path,
        help="Optional path to write a JSON report",
    )
    parser.add_argument(
        "--expect-aligned",
        action="store_true",
        help="Exit non-zero when desired and actual state differ",
    )
    args = parser.parse_args(argv)

    config_errors = validate(args.root)
    if config_errors:
        for error in config_errors:
            print(f"error: {error}", file=sys.stderr)
        print("BLOCKED: configuration invalid; refusing audit", file=sys.stderr)
        return 2

    allowlist = allowlisted_repos(load_yaml(args.root / "config/github/repos.yml"))
    if args.repo not in allowlist:
        print(
            f"BLOCKED: repository {args.repo!r} is not in the allowlist",
            file=sys.stderr,
        )
        return 2

    if not args.token:
        print(
            "BLOCKED: no GitHub token available for live audit "
            "(set GITHUB_TOKEN or pass --token)",
            file=sys.stderr,
        )
        return 3

    try:
        report = run_audit(
            root=args.root,
            repo=args.repo,
            token=args.token,
            api_url=args.api_url.rstrip("/"),
        )
    except AuditError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 4

    text = json.dumps(report, indent=2, sort_keys=True)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")

    if report["status"] == "drift" and args.expect_aligned:
        return 5
    if report["status"] == "error":
        return 4
    return 0


class AuditError(RuntimeError):
    """Raised when the live audit cannot complete."""


def run_audit(*, root: Path, repo: str, token: str, api_url: str) -> dict[str, Any]:
    settings = load_yaml(root / "config/github/settings-config.yml")
    desired_paths = ruleset_paths_from_settings(settings, root=root)
    desired_by_name: dict[str, dict[str, Any]] = {}
    for path in desired_paths:
        payload = load_json(path)
        desired_by_name[str(payload["name"])] = payload

    try:
        actual_list = api_get(api_url, f"/repos/{repo}/rulesets", token)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code in {401, 403}:
            raise AuditError(
                f"BLOCKED: insufficient permission to list rulesets for {repo} "
                f"(HTTP {exc.code}). Need Administration: read (or write for APPLY). "
                f"Body: {body}"
            ) from exc
        raise AuditError(f"unexpected API error listing rulesets: HTTP {exc.code}: {body}") from exc

    if not isinstance(actual_list, list):
        raise AuditError("rulesets list response was not a JSON array")

    actual_by_name: dict[str, dict[str, Any]] = {}
    for summary in actual_list:
        name = summary.get("name")
        ruleset_id = summary.get("id")
        if not name or ruleset_id is None:
            continue
        try:
            detail = api_get(api_url, f"/repos/{repo}/rulesets/{ruleset_id}", token)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise AuditError(
                f"failed to read ruleset {name!r} ({ruleset_id}): HTTP {exc.code}: {body}"
            ) from exc
        actual_by_name[str(name)] = detail

    diffs: dict[str, list[str]] = {}
    for name, desired in desired_by_name.items():
        diffs[name] = compare_rulesets(desired, actual_by_name.get(name))

    unmanaged = sorted(set(actual_by_name) - set(desired_by_name))
    aligned = all(not items for items in diffs.values())
    status = "aligned" if aligned else "drift"

    return {
        "mode": "AUDIT",
        "repository": repo,
        "status": status,
        "desired_rulesets": sorted(desired_by_name),
        "actual_rulesets": sorted(actual_by_name),
        "unmanaged_actual_rulesets": unmanaged,
        "diffs": diffs,
        "note": (
            "Unmanaged rulesets are reported but not deleted. "
            "delete-unmanaged-rulesets stays false in the pilot."
        ),
    }


def api_get(api_url: str, path: str, token: str) -> Any:
    request = urllib.request.Request(
        f"{api_url}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": API_VERSION,
            "User-Agent": "gmv-github-moderator",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


if __name__ == "__main__":
    raise SystemExit(main())
