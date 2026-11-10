#!/usr/bin/env python3
"""Validate the Greenfield baseline layout, ADR invariants, and obvious secrets."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    ".gitignore",
    ".gitattributes",
    ".markdownlint-cli2.jsonc",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/ci.yml",
    "docs/README.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA_MODEL.md",
    "docs/WORKITEM_LIFECYCLE.md",
    "docs/IDENTITY_MODEL.md",
    "docs/API_SPECIFICATION.md",
    "docs/GOVERNANCE.md",
    "docs/adr/README.md",
    "docs/adr/template.md",
    "app/README.md",
    "app/__init__.py",
    "app/main.py",
    "app/config.py",
    "app/db.py",
    "app/logging_config.py",
    "app/lifecycle.py",
    "tests/README.md",
    "tests/test_health.py",
    "tests/test_ready.py",
    "tests/test_migration.py",
    "tests/test_lifecycle_contract.py",
    "api/openapi.yaml",
    "scripts/validate_structure.py",
    "pyproject.toml",
    "Dockerfile",
    ".dockerignore",
    ".env.example",
    "alembic.ini",
    "migrations/env.py",
    "migrations/versions/0001_schema_meta.py",
)

REQUIRED_DIRS = (
    "docs",
    "docs/adr",
    "api",
    "app",
    "tests",
    "scripts",
    "migrations",
    "migrations/versions",
    ".github",
    ".github/workflows",
)

# Status is an invariant of this baseline. Changing it is a deliberate edit of
# this map in the same pull request as the ADR.
ADR_STATUS = {
    "docs/adr/0001-postgresql-on-railway.md": "Accepted",
    "docs/adr/0002-python-fastapi.md": "Accepted",
    "docs/adr/0003-single-assignment-authority.md": "Accepted",
    "docs/adr/0004-branch-protection-codeowners.md": "Proposed",
    "docs/adr/0005-railway-environments.md": "Proposed",
    "docs/adr/0006-backup-retention-rpo-rto.md": "Proposed",
    "docs/adr/0007-secret-management.md": "Proposed",
    "docs/adr/0008-auth-standard.md": "Proposed",
    "docs/adr/0009-migration-compatibility.md": "Proposed",
    "docs/adr/0010-slo-alerting-incident.md": "Proposed",
    "docs/adr/0011-release-rollback-authority.md": "Proposed",
    "docs/adr/0012-hosting-region-usa.md": "Accepted",
    "docs/adr/0013-repository-visibility-public.md": "Accepted",
}

ADR_MARKERS = {
    "docs/adr/0002-python-fastapi.md": ("GF-006",),
    "docs/adr/0009-migration-compatibility.md": ("schema_meta",),
    "docs/adr/0012-hosting-region-usa.md": ("sfo", "DSGVO", "Latenz", "derselben Region"),
}

ADR_FILENAME = re.compile(r"^\d{4}-[a-z0-9-]+\.md$")
STATUS_LINE = re.compile(r"^- Status: (Proposed|Accepted|Rejected|Superseded)$")
REQUIRED_HEADINGS = ("## Kontext", "## Entscheidung", "## Konsequenzen")
SKIP_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
}
SKIP_SUFFIXES = {".pyc", ".pyo"}
FORBIDDEN_NAMES = {
    ".env",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
    "credentials.json",
}
SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"\bsk_live_[A-Za-z0-9]{8,}\b"),
)


def main() -> int:
    errors: list[str] = []
    require_paths(errors)
    check_runtime_files(errors)
    check_adrs(errors)
    check_codeowners(errors)
    check_workflow(errors)
    scan_tree(errors)
    if errors:
        for err in errors:
            print(f"error: {err}", file=sys.stderr)
        print(f"{len(errors)} structure error(s)", file=sys.stderr)
        return 1
    print("structure ok")
    return 0


def require_paths(errors: list[str]) -> None:
    for relative in REQUIRED_FILES:
        if not (ROOT / relative).is_file():
            errors.append(f"missing file: {relative}")
    for relative in REQUIRED_DIRS:
        if not (ROOT / relative).is_dir():
            errors.append(f"missing directory: {relative}")


def check_runtime_files(errors: list[str]) -> None:
    dockerfile = ROOT / "Dockerfile"
    if dockerfile.is_file():
        text = read_text(dockerfile, errors)
        if text is not None:
            for snippet in ("USER app", "/health", "${PORT:-8000}"):
                if snippet not in text:
                    errors.append(f"Dockerfile does not contain {snippet!r}")
    example = ROOT / ".env.example"
    if example.is_file():
        text = read_text(example, errors)
        placeholder = "DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME"
        if text is not None and placeholder not in text:
            errors.append(".env.example DATABASE_URL must stay a placeholder")


def check_adrs(errors: list[str]) -> None:
    adr_dir = ROOT / "docs" / "adr"
    if not adr_dir.is_dir():
        return
    numbered = sorted(
        path for path in adr_dir.glob("*.md") if ADR_FILENAME.match(path.name)
    )
    found = {path.relative_to(ROOT).as_posix() for path in numbered}
    expected = set(ADR_STATUS)
    if found != expected:
        missing = sorted(expected - found)
        extra = sorted(found - expected)
        if missing:
            errors.append(f"ADR map missing files: {missing}")
        if extra:
            errors.append(f"numbered ADR not in status map: {extra}")

    index_path = adr_dir / "README.md"
    index = index_path.read_text(encoding="utf-8") if index_path.is_file() else ""
    for path in numbered:
        relative = path.relative_to(ROOT).as_posix()
        text = read_text(path, errors)
        if text is None:
            continue
        if relative in ADR_STATUS:
            check_adr_file(relative, text, errors)
        if path.name not in index:
            errors.append(f"docs/adr/README.md does not link {path.name}")

    template_path = adr_dir / "template.md"
    if template_path.is_file():
        template = read_text(template_path, errors)
        if template is not None:
            for heading in REQUIRED_HEADINGS:
                if heading not in template.splitlines():
                    errors.append(f"docs/adr/template.md missing heading {heading}")
            if "Diese Datei ist keine Entscheidung." not in template:
                errors.append(
                    "docs/adr/template.md must state that it is not a decision"
                )
            if "template.md" not in index:
                errors.append("docs/adr/README.md does not link template.md")


def check_adr_file(relative: str, text: str, errors: list[str]) -> None:
    for heading in REQUIRED_HEADINGS:
        if heading not in text.splitlines():
            errors.append(f"{relative} missing heading {heading}")
    statuses = [
        match.group(1)
        for line in text.splitlines()[:15]
        if (match := STATUS_LINE.match(line))
    ]
    if len(statuses) != 1:
        errors.append(f"{relative} needs exactly one status line in the first 15 lines")
        return
    expected = ADR_STATUS[relative]
    if statuses[0] != expected:
        errors.append(f"{relative} status is {statuses[0]}, expected {expected}")
        return
    decision = section_body(text, "## Entscheidung")
    first = next((line for line in decision.splitlines() if line.strip()), "")
    if expected == "Proposed" and not first.startswith("Nicht entschieden."):
        errors.append(f"{relative} decision must start with 'Nicht entschieden.'")
    if expected == "Accepted" and not first.startswith("Entschieden."):
        errors.append(f"{relative} decision must start with 'Entschieden.'")
    for marker in ADR_MARKERS.get(relative, ()):
        if marker not in text:
            errors.append(f"{relative} is missing required marker {marker!r}")


def section_body(text: str, heading: str) -> str:
    collecting = False
    body: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if collecting:
                break
            collecting = line == heading
            continue
        if collecting:
            body.append(line)
    return "\n".join(body).strip()


def check_codeowners(errors: list[str]) -> None:
    path = ROOT / ".github" / "CODEOWNERS"
    if not path.is_file():
        return
    text = read_text(path, errors)
    if text is None:
        return
    if "Entwurf" not in text:
        errors.append(".github/CODEOWNERS must stay marked as a draft")
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        errors.append(
            f".github/CODEOWNERS:{number} has an active rule; owners stay commented "
            "until ADR-0004 is accepted"
        )


def check_workflow(errors: list[str]) -> None:
    path = ROOT / ".github" / "workflows" / "ci.yml"
    if not path.is_file():
        return
    text = read_text(path, errors)
    if text is None:
        return
    required_snippets = (
        "contents: read",
        "markdownlint-cli2@0.24.0",
        "python3 scripts/validate_structure.py",
        "pull_request:",
        "postgres:18",
        "ruff check",
        "pytest",
        "docker build",
        "openapi-spec-validator api/openapi.yaml",
    )
    for snippet in required_snippets:
        if snippet not in text:
            errors.append(f".github/workflows/ci.yml does not contain {snippet!r}")
    if re.search(r"contents:\s*write", text):
        errors.append(".github/workflows/ci.yml must not grant contents: write")


def scan_tree(errors: list[str]) -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in SKIP_SUFFIXES:
            continue
        if path.name in FORBIDDEN_NAMES or path.suffix.lower() in {".pem", ".key", ".p12", ".pfx"}:
            errors.append(f"forbidden file: {relative.as_posix()}")
        text = read_text(path, errors)
        if text is None:
            continue
        for pattern in SECRET_PATTERNS:
            if pattern.search(text):
                errors.append(f"possible secret in {relative.as_posix()}")
                break
        if path.suffix == ".md":
            first = next((line for line in text.splitlines() if line.strip()), "")
            if not re.match(r"^# [^#]", first):
                errors.append(f"{relative.as_posix()} must start with one H1")


def read_text(path: Path, errors: list[str]) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeError:
        errors.append(f"{path.relative_to(ROOT).as_posix()} is not UTF-8")
        return None


if __name__ == "__main__":
    sys.exit(main())
