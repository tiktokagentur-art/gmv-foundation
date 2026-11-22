"""CRG-001A offline-only review observation validator; NEVER a merge gate."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REQUIRED_CHECKS = frozenset({"Lint and structure", "Backend", "Image"})
SHA_PATTERN = re.compile(r"[0-9a-f]{40}\Z")
REVIEW_FRAGMENT = re.compile(r"pullrequestreview-[1-9][0-9]*\Z")
REQUIRED_KEYS = frozenset(
    {
        "schema_version",
        "source",
        "repository",
        "pr_number",
        "head_sha",
        "author_id",
        "risk_class",
        "reviewer_id",
        "review_commit_sha",
        "review_url",
        "review_state",
        "passed_checks",
        "unresolved_findings",
        "synthetic",
    }
)
STATES = frozenset({"APPROVED", "COMMENTED", "CHANGES_REQUESTED", "DISMISSED"})
RISKS = frozenset({"R0", "R1", "R2", "R3", "R4"})


def _sha(value: Any) -> bool:
    return isinstance(value, str) and SHA_PATTERN.fullmatch(value) is not None


def _review_url(value: Any, repo: str, number: int) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.netloc == "github.com"
        and parsed.path == f"/{repo}/pull/{number}"
        and parsed.query == ""
        and REVIEW_FRAGMENT.fullmatch(parsed.fragment) is not None
    )


def evaluate_observation(
    evidence: Any,
    *,
    expected_repository: str,
    expected_pr: int,
    expected_head_sha: str,
    expected_author_id: str,
) -> dict[str, Any]:
    """Evaluate shape/consistency only, not provenance or formal GitHub approval.

    A forged JSON payload can pass shape checks. Thus even consistent evidence
    is untrusted and merge_authorized is always False.
    """
    errors: list[str] = []
    if not isinstance(evidence, dict):
        return {
            "verdict": "DENY",
            "merge_authorized": False,
            "reasons": ["invalid_payload", "github_source_not_authenticated"],
        }

    if set(evidence) != REQUIRED_KEYS:
        errors.append("invalid_keys")
    if type(evidence.get("schema_version")) is not int or evidence.get("schema_version") != 1:
        errors.append("unsupported_schema_version")
    if evidence.get("source") != "github_api_snapshot":
        errors.append("unknown_source")
    if evidence.get("repository") != expected_repository:
        errors.append("repository_mismatch")
    if type(evidence.get("pr_number")) is not int or evidence.get("pr_number") != expected_pr:
        errors.append("pr_mismatch")
    if not _sha(evidence.get("head_sha")) or evidence["head_sha"] != expected_head_sha:
        errors.append("head_sha_mismatch")
    author = evidence.get("author_id")
    reviewer = evidence.get("reviewer_id")
    if not isinstance(author, str) or not author or author != expected_author_id:
        errors.append("author_mismatch")
    if not isinstance(reviewer, str) or not reviewer or reviewer == author:
        errors.append("self_or_missing_reviewer")
    if (
        not _sha(evidence.get("review_commit_sha"))
        or evidence["review_commit_sha"] != expected_head_sha
    ):
        errors.append("stale_or_invalid_review")
    if not _review_url(evidence.get("review_url"), expected_repository, expected_pr):
        errors.append("invalid_review_url")
    if not isinstance(evidence.get("review_state"), str) or evidence["review_state"] not in STATES:
        errors.append("invalid_review_state")
    if evidence.get("review_state") in ("CHANGES_REQUESTED", "DISMISSED"):
        errors.append("review_not_positive")
    if not isinstance(evidence.get("risk_class"), str) or evidence["risk_class"] not in RISKS:
        errors.append("invalid_risk_class")
    if evidence.get("risk_class") in ("R2", "R3", "R4"):
        errors.append("additional_security_review_required")
    checks = evidence.get("passed_checks")
    if (
        not isinstance(checks, list)
        or any(not isinstance(check, str) for check in checks)
        or not REQUIRED_CHECKS.issubset(set(checks))
    ):
        errors.append("required_checks_missing")
    if type(evidence.get("unresolved_findings")) is not int or evidence["unresolved_findings"] != 0:
        errors.append("unresolved_or_invalid_findings")
    if type(evidence.get("synthetic")) is not bool or evidence["synthetic"]:
        errors.append("synthetic_or_invalid_evidence")

    # Inputs are untrusted JSON, not an authenticated GitHub API response.
    # This constant DENY must not be turned into a production approval.
    errors.append("github_source_not_authenticated")
    return {
        "verdict": "DENY",
        "merge_authorized": False,
        "reasons": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, help="untrusted offline JSON fixture")
    parser.add_argument("--expected-repository", required=True)
    parser.add_argument("--expected-pr", type=int, required=True)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--expected-author-id", required=True)
    args = parser.parse_args()
    payload = json.loads(args.evidence.read_text(encoding="utf-8"))
    print(
        json.dumps(
            evaluate_observation(
                payload,
                expected_repository=args.expected_repository,
                expected_pr=args.expected_pr,
                expected_head_sha=args.expected_head_sha,
                expected_author_id=args.expected_author_id,
            ),
            sort_keys=True,
        )
    )
    # Never produce a passing CI status when used as a required gate.
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
