"""Conservative risk classifier; not a GitHub permission mechanism."""
from pathlib import PurePosixPath

from app.pr_review.schemas import Change, Risk

# These are candidate categories only. They are not CEO-approved merge policies.
_CRITICAL = (
    ".github/", "migrations/", "infra/", "infrastructure/", "deploy/",
    "security/", "scripts/", "api/", "app/", "requirements",
    "pyproject.toml", "Dockerfile", "SECURITY.md", "CONTRIBUTING.md",
    "docs/adr/", "docs/GOVERNANCE.md",
)
_R0_PREFIX = ("docs/guides/", "docs/tutorials/")
_R1_PREFIX = ("tests/fixtures/", "tests/mocks/")


def classify(changes: tuple[Change, ...]) -> Risk:
    if not changes:
        return Risk.R4
    highest = Risk.R0
    for change in changes:
        path = change.path
        if (
            path.startswith("/")
            or "\\" in path
            or "//" in path
            or PurePosixPath(path).as_posix() != path
            or any(part in (".", "..") for part in path.split("/"))
            or any(ord(char) < 32 for char in path)
        ):
            return Risk.R4
        if change.status in ("removed", "renamed"):
            return Risk.R3
        if path.startswith(_CRITICAL):
            highest = max(highest, Risk.R3)
        elif path.startswith(_R0_PREFIX) and path.endswith(".md"):
            highest = max(highest, Risk.R0)
        elif path.startswith(_R1_PREFIX) and path.endswith((".json", ".py", ".yaml")):
            highest = max(highest, Risk.R1)
        elif path.startswith("docs/") and path.endswith(".md"):
            highest = max(highest, Risk.R2)
        else:
            return Risk.R4
    return highest
