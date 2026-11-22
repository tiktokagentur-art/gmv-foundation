#!/usr/bin/env python3
"""Check required handbook pages and relative Markdown links."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "docs/developer/README.md",
    "docs/developer/onboarding.md",
    "docs/developer/systems.md",
    "docs/developer/automation.md",
    "docs/developer/factories/README.md",
    "docs/developer/factories/control-plane.md",
    "docs/developer/factories/software-factory.md",
    "docs/developer/factories/content-factory.md",
    "docs/developer/templates/README.md",
    "docs/developer/templates/factory.md",
    "docs/developer/templates/api.md",
    "docs/developer/templates/agent.md",
)
LINK = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")


def check_links(page: Path, root: Path) -> list[str]:
    errors: list[str] = []
    in_fence = False
    for line_no, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        for match in LINK.finditer(line):
            target = match.group(1).strip().split(" ", 1)[0].strip("<>")
            if not target or target.startswith("#"):
                continue
            parsed = urlsplit(target)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            if parsed.path.startswith("/"):
                errors.append(f"{page.relative_to(root)}:{line_no}: absolute: {target}")
                continue
            path = (page.parent / unquote(parsed.path)).resolve()
            if not path.is_relative_to(root.resolve()):
                errors.append(f"{page.relative_to(root)}:{line_no}: outside repo: {target}")
            elif not path.exists():
                errors.append(f"{page.relative_to(root)}:{line_no}: missing: {target}")
    return errors


def validate(root: Path) -> list[str]:
    errors = [f"missing: {p}" for p in REQUIRED if not (root / p).is_file()]
    pages = [root / "README.md", root / "docs/README.md"]
    pages.extend(sorted((root / "docs/developer").rglob("*.md")))
    for page in pages:
        if page.is_file():
            errors.extend(check_links(page, root))
    return errors


if __name__ == "__main__":
    issues = validate(ROOT)
    for issue in issues:
        print(f"error: {issue}", file=sys.stderr)
    if issues:
        raise SystemExit(1)
    print("handbook structure and links ok")
