#!/usr/bin/env python3
"""Security policy for the GMV GitHub Moderator.

Encodes trust boundaries that must hold in CI and in the Actions workflow:

- Pull requests never receive privileged GitHub App credentials, including
  same-repository PRs.
- Configuration validation and unit tests never require privileged credentials.
- Privileged App tokens are only minted on protected execution paths.
- APPLY requires main + environment approval + CEO gate + App credentials.
- Workflow must not use pull_request_target with untrusted checkout/execution.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from github_moderator_lib import PILOT_REPO, ROOT  # noqa: E402

WORKFLOW_PATH = ROOT / ".github" / "workflows" / "github-moderator.yml"
APPLY_ENVIRONMENT = "github-moderator-apply"
PRIVILEGED_ENVIRONMENT = "github-moderator-privileged"
APPLY_GATE_ENABLED = "enabled"
PRIVILEGED_EVENTS = frozenset({"workflow_dispatch", "schedule", "push"})
UNTRUSTED_EVENTS = frozenset({"pull_request", "pull_request_target"})
TOKEN_LEAK_PATTERNS = (
    re.compile(r"echo\s+[\"']?token=", re.IGNORECASE),
    re.compile(r"GITHUB_OUTPUT[^\n]*token=", re.IGNORECASE),
    re.compile(r"::set-output\s+name=token::", re.IGNORECASE),
    re.compile(
        r"printf\s+[^\n]*\$\{\{\s*steps\.[^}]+\.outputs\.token",
        re.IGNORECASE,
    ),
)


@dataclass(frozen=True)
class TrustDecision:
    """Result of evaluating whether privileged credentials may be used."""

    privileged_allowed: bool
    reason: str
    blocked: bool = False


@dataclass(frozen=True)
class ApplyDecision:
    """Result of evaluating APPLY prerequisites."""

    allowed: bool
    status: str
    reasons: tuple[str, ...]


def allows_privileged_credentials(
    event_name: str,
    *,
    head_repo: str | None = None,
    repository: str | None = None,
    ref: str | None = None,
) -> TrustDecision:
    """Decide whether a run may mint or use GitHub App credentials.

    Same-repository pull requests are intentionally *not* trusted. PR code is
    untrusted regardless of fork vs. same-repo origin.
    """
    event = (event_name or "").strip()
    if event in UNTRUSTED_EVENTS:
        same_repo = bool(
            head_repo and repository and head_repo.strip() == repository.strip()
        )
        origin = "same-repository" if same_repo else "fork-or-external"
        return TrustDecision(
            privileged_allowed=False,
            blocked=True,
            reason=(
                f"BLOCKED: event {event!r} ({origin}) must not receive "
                "privileged GitHub App credentials"
            ),
        )
    if event not in PRIVILEGED_EVENTS:
        return TrustDecision(
            privileged_allowed=False,
            blocked=True,
            reason=f"BLOCKED: event {event!r} is not a privileged execution path",
        )
    if event == "push" and ref and ref != "refs/heads/main":
        return TrustDecision(
            privileged_allowed=False,
            blocked=True,
            reason=(
                f"BLOCKED: push to {ref!r} is not a privileged path "
                "(only refs/heads/main)"
            ),
        )
    return TrustDecision(
        privileged_allowed=True,
        reason=f"privileged path allowed for event {event!r}",
    )


def evaluate_apply_gate(
    *,
    event_name: str,
    mode: str,
    ref: str,
    apply_gate: str | None,
    environment_name: str | None,
    environment_approved: bool,
    has_app_credentials: bool,
    repository: str = PILOT_REPO,
) -> ApplyDecision:
    """Evaluate every APPLY prerequisite. Missing any condition → BLOCKED."""
    reasons: list[str] = []

    if (mode or "").strip() != "APPLY":
        reasons.append(f"mode must be APPLY (got {mode!r})")
    if (event_name or "").strip() != "workflow_dispatch":
        reasons.append(
            f"APPLY requires workflow_dispatch (got {event_name!r})"
        )
    if (ref or "").strip() != "refs/heads/main":
        reasons.append(
            f"APPLY is only allowed from refs/heads/main (got {ref!r})"
        )
    if (apply_gate or "").strip() != APPLY_GATE_ENABLED:
        reasons.append(
            "GMV_MODERATOR_APPLY_GATE must be 'enabled' "
            f"(got {apply_gate!r})"
        )
    if (environment_name or "").strip() != APPLY_ENVIRONMENT:
        reasons.append(
            f"environment must be {APPLY_ENVIRONMENT!r} "
            f"(got {environment_name!r})"
        )
    if not environment_approved:
        reasons.append(
            "environment approval is required "
            f"(server-enforced reviewers on {APPLY_ENVIRONMENT})"
        )
    if not has_app_credentials:
        reasons.append("GitHub App credentials are required for APPLY")
    if repository != PILOT_REPO:
        reasons.append(
            f"repository {repository!r} is outside the allowlist pilot scope"
        )

    trust = allows_privileged_credentials(event_name, repository=repository)
    if not trust.privileged_allowed:
        reasons.append(trust.reason)

    if reasons:
        return ApplyDecision(
            allowed=False,
            status="BLOCKED",
            reasons=tuple(reasons),
        )
    return ApplyDecision(
        allowed=True,
        status="ALLOWED",
        reasons=("all APPLY prerequisites satisfied",),
    )


def assert_no_token_leak(text: str, *, label: str = "output") -> None:
    """Raise ValueError if text appears to publish a token."""
    lowered = text.lower()
    for needle in (
        "ghs_",
        "github_pat_",
        "-----begin rsa private key-----",
        "-----begin private key-----",
    ):
        if needle in lowered:
            raise ValueError(f"BLOCKED: possible credential material in {label}")
    for pattern in TOKEN_LEAK_PATTERNS:
        if pattern.search(text):
            raise ValueError(
                f"BLOCKED: token publication pattern detected in {label}"
            )


def analyze_workflow_security(
    workflow_text: str,
    *,
    path: str = ".github/workflows/github-moderator.yml",
) -> list[str]:
    """Static security checks against the moderator workflow document."""
    errors: list[str] = []
    text = workflow_text

    if re.search(r"(?m)^\s*pull_request_target\s*:", text):
        errors.append(
            f"{path}: pull_request_target is forbidden "
            "(must not checkout or execute untrusted PR code with privileges)"
        )

    if APPLY_ENVIRONMENT not in text:
        errors.append(
            f"{path}: APPLY job must declare environment "
            f"{APPLY_ENVIRONMENT!r}"
        )

    if PRIVILEGED_ENVIRONMENT not in text:
        errors.append(
            f"{path}: privileged AUDIT/DRY_RUN jobs must use environment "
            f"{PRIVILEGED_ENVIRONMENT!r} so App secrets are not repo-global"
        )

    if "GMV_MODERATOR_APPLY_GATE" not in text:
        errors.append(f"{path}: APPLY gate variable check is missing")

    if "refs/heads/main" not in text:
        errors.append(f"{path}: APPLY must enforce refs/heads/main")

    # Secret-using jobs must be gated by event_name, not only by a Python
    # helper that pull_request code could rewrite.
    if "github.event_name != 'pull_request'" not in text and (
        'github.event_name != "pull_request"' not in text
    ):
        errors.append(
            f"{path}: secret-using jobs must gate on "
            "github.event_name != 'pull_request' in the workflow expression"
        )

    if "secrets.GMV_GITHUB_MODERATOR_APP_PRIVATE_KEY" in text:
        if "outputs.privileged" not in text:
            errors.append(
                f"{path}: privileged-path gate output is required before "
                "referencing GitHub App secrets"
            )

    for pattern in TOKEN_LEAK_PATTERNS:
        if pattern.search(text):
            errors.append(
                f"{path}: must not publish tokens to GITHUB_OUTPUT or logs "
                f"(matched {pattern.pattern!r})"
            )

    # PRs must not be auto-trusted via same-repo comparison alone.
    if re.search(
        r"trusted\s*=\s*true",
        text,
    ) and re.search(
        r"head\.repo\.full_name|REPO_TRUSTED",
        text,
    ):
        errors.append(
            f"{path}: must not treat same-repository pull requests as trusted "
            "for privileged credentials"
        )

    if "repositories: gmv-foundation" not in text:
        errors.append(
            f"{path}: GitHub App token minting must scope repositories "
            "to gmv-foundation"
        )

    if "pull_request:" in text and "privileged=false" not in text:
        errors.append(
            f"{path}: resolve step must force privileged=false on "
            "pull_request paths"
        )

    return errors


def validate_workflow_file(root: Path | None = None) -> list[str]:
    """Load and analyze the checked-in moderator workflow."""
    base = root if root is not None else ROOT
    path = base / ".github" / "workflows" / "github-moderator.yml"
    if not path.is_file():
        return [f"missing {path.as_posix()}"]
    return analyze_workflow_security(
        path.read_text(encoding="utf-8"),
        path=str(path.relative_to(base))
        if path.is_relative_to(base)
        else path.as_posix(),
    )


def refuse_privileged_use_from_pr_code(
    *,
    event_name: str,
    attempting_action: str,
    head_repo: str | None = None,
    repository: str | None = None,
) -> TrustDecision:
    """Explicit denial helper for tests simulating PR code token abuse."""
    decision = allows_privileged_credentials(
        event_name,
        head_repo=head_repo,
        repository=repository,
    )
    if decision.privileged_allowed:
        return TrustDecision(
            privileged_allowed=False,
            blocked=True,
            reason=(
                f"BLOCKED: refusing privileged action {attempting_action!r} "
                f"on unexpected path {event_name!r}"
            ),
        )
    return TrustDecision(
        privileged_allowed=False,
        blocked=True,
        reason=(
            f"BLOCKED: PR code must not perform privileged action "
            f"{attempting_action!r}; {decision.reason}"
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    check_trust = sub.add_parser(
        "check-trust",
        help="Evaluate whether privileged credentials are allowed",
    )
    check_trust.add_argument("--event", required=True)
    check_trust.add_argument("--head-repo")
    check_trust.add_argument("--repository", default=PILOT_REPO)
    check_trust.add_argument("--ref")

    check_apply = sub.add_parser(
        "check-apply",
        help="Evaluate APPLY gate prerequisites",
    )
    check_apply.add_argument("--event", required=True)
    check_apply.add_argument("--mode", required=True)
    check_apply.add_argument("--ref", required=True)
    check_apply.add_argument("--gate", default="")
    check_apply.add_argument(
        "--environment-name",
        default=APPLY_ENVIRONMENT,
    )
    check_apply.add_argument(
        "--environment-approved",
        choices=("true", "false"),
        default="false",
    )
    check_apply.add_argument(
        "--has-app-credentials",
        choices=("true", "false"),
        default="false",
    )
    check_apply.add_argument("--repository", default=PILOT_REPO)

    check_workflow = sub.add_parser(
        "check-workflow",
        help="Statically analyze the moderator workflow for security invariants",
    )
    check_workflow.add_argument(
        "--root",
        type=Path,
        default=ROOT,
        help="Repository root",
    )

    args = parser.parse_args(argv)

    if args.command == "check-trust":
        decision = allows_privileged_credentials(
            args.event,
            head_repo=args.head_repo,
            repository=args.repository,
            ref=args.ref,
        )
        print(decision.reason)
        return 0 if decision.privileged_allowed else 2

    if args.command == "check-apply":
        decision = evaluate_apply_gate(
            event_name=args.event,
            mode=args.mode,
            ref=args.ref,
            apply_gate=args.gate,
            environment_name=args.environment_name,
            environment_approved=args.environment_approved == "true",
            has_app_credentials=args.has_app_credentials == "true",
            repository=args.repository,
        )
        for reason in decision.reasons:
            print(reason)
        print(f"status={decision.status}")
        return 0 if decision.allowed else 2

    if args.command == "check-workflow":
        errors = validate_workflow_file(args.root)
        if errors:
            for error in errors:
                print(f"error: {error}", file=sys.stderr)
            print(
                f"{len(errors)} github-moderator workflow security error(s)",
                file=sys.stderr,
            )
            return 1
        print("github-moderator workflow security ok")
        return 0

    raise AssertionError(f"unhandled command {args.command!r}")


def as_public_dict(decision: ApplyDecision | TrustDecision) -> dict[str, Any]:
    """Serialize a decision without embedding secrets."""
    if isinstance(decision, TrustDecision):
        return {
            "privileged_allowed": decision.privileged_allowed,
            "blocked": decision.blocked,
            "reason": decision.reason,
        }
    return {
        "allowed": decision.allowed,
        "status": decision.status,
        "reasons": list(decision.reasons),
    }


if __name__ == "__main__":
    raise SystemExit(main())
