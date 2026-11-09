"""The lifecycle document and the OpenAPI enum match the code contract."""

from __future__ import annotations

from pathlib import Path

import yaml

from app.lifecycle import FENCING_RULES, TERMINAL_STATUSES, TRANSITIONS, WorkItemStatus

ROOT = Path(__file__).resolve().parents[1]
LIFECYCLE_DOC = ROOT / "docs" / "WORKITEM_LIFECYCLE.md"
OPENAPI = ROOT / "api" / "openapi.yaml"


def test_documented_transitions_match_code() -> None:
    assert _table(LIFECYCLE_DOC.read_text(encoding="utf-8"), "## Übergänge", 3) == set(TRANSITIONS)


def test_documented_fencing_rules_match_code() -> None:
    assert _table(LIFECYCLE_DOC.read_text(encoding="utf-8"), "## Fencing", 2) == set(FENCING_RULES)


def test_terminal_statuses_have_no_outgoing_transition() -> None:
    outgoing = {source for source, _target, _actor in TRANSITIONS}
    assert outgoing.isdisjoint({status.value for status in TERMINAL_STATUSES})


def test_every_status_is_documented_and_declared_in_openapi() -> None:
    document = LIFECYCLE_DOC.read_text(encoding="utf-8")
    values = {status.value for status in WorkItemStatus}
    for value in values:
        assert f"`{value}`" in document
    spec = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    declared = set(spec["components"]["schemas"]["WorkItemStatus"]["enum"])
    assert declared == values


def _table(text: str, heading: str, width: int) -> set[tuple[str, ...]]:
    lines = text.splitlines()
    try:
        start = lines.index(heading)
    except ValueError as exc:
        raise AssertionError(f"missing heading {heading}") from exc
    rows: set[tuple[str, ...]] = set()
    seen_header = False
    for line in lines[start + 1 :]:
        if line.startswith("## "):
            break
        if not line.startswith("|"):
            if seen_header and rows:
                break
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if not seen_header:
            seen_header = True
            continue
        if cells and set(cells[0]) <= {"-", ":"}:
            continue
        rows.add(tuple(cells[:width]))
    return rows
