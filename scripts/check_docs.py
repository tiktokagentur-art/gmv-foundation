#!/usr/bin/env python3
"""Check required handbook pages and local Markdown link destinations."""

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

# Check inline links and reference definitions for local file destinations.
INLINE_LINK = re.compile(r"!?\[[^\]\n]*\]\(\s*")
REFERENCE = re.compile(r"^[ \t]{0,3}\[[^\]\n]+\]:[ \t]*(<[^>\n]+>|[^\s]+)")
BACKTICKS = re.compile(r"(?<!\\)`+")
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")


def mask_inline_code(line: str) -> str:
    """Mask backtick-delimited code spans, including multi-tick spans."""
    runs = list(BACKTICKS.finditer(line))
    masked = list(line)
    i = 0
    while i < len(runs):
        opening = runs[i]
        closing = next(
            (j for j in range(i + 1, len(runs)) if len(runs[j].group()) == len(opening.group())),
            None,
        )
        if closing is None:
            i += 1
            continue
        for pos in range(opening.start(), runs[closing].end()):
            masked[pos] = " "
        i = closing + 1
    return "".join(masked)


def inline_target(line: str, start: int) -> str | None:
    """Read a Markdown destination without splitting angle-bracketed spaces."""
    if start >= len(line):
        return None

    if line[start] == "<":
        end = line.find(">", start + 1)
        if end < 0 or ")" not in line[end + 1 :]:
            return None
        return line[start + 1 : end]

    target: list[str] = []
    depth = 0
    for char in line[start:]:
        if char.isspace() and depth == 0:
            break
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return "".join(target)
            depth -= 1
        target.append(char)

    # Nonempty destinations can be followed by an optional title.
    return "".join(target) if target and ")" in line[start:] else None


def check_target(target: str, page: Path, root: Path, line_no: int) -> str | None:
    """Check a local link and return a diagnostic, if needed."""
    if not target or target.startswith("#"):
        return None
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc or not parsed.path:
        return None
    prefix = f"{page.relative_to(root)}:{line_no}"
    if parsed.path.startswith("/"):
        return f"{prefix}: absolute: {target}"
    destination = (page.parent / unquote(parsed.path)).resolve()
    if not destination.is_relative_to(root.resolve()):
        return f"{prefix}: outside repo: {target}"
    if not destination.exists():
        return f"{prefix}: missing: {target}"
    return None


def check_links(page: Path, root: Path) -> list[str]:
    """Validate local inline links and reference destinations in Markdown."""
    errors: list[str] = []
    fence: tuple[str, int] | None = None
    for line_no, line in enumerate(page.read_text(encoding="utf-8").splitlines(), 1):
        marker = FENCE.match(line)
        if fence:
            if (
                marker
                and marker.group(1)[0] == fence[0]
                and len(marker.group(1)) >= fence[1]
                and not marker.group(2).strip()
            ):
                fence = None
            continue
        if marker:
            fence = (marker.group(1)[0], len(marker.group(1)))
            continue

        visible = mask_inline_code(line)
        definition = REFERENCE.match(visible)
        if definition:
            raw = definition.group(1)
            target = raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw
            error = check_target(target, page, root, line_no)
            if error is not None:
                errors.append(error)
            continue

        for link in INLINE_LINK.finditer(visible):
            target = inline_target(visible, link.end())
            if target is None:
                continue
            error = check_target(target, page, root, line_no)
            if error is not None:
                errors.append(error)
    return errors


def validate(root: Path) -> list[str]:
    """Validate the handbook and its root navigation entry points."""
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
