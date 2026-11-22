"""Offline conformance checks for CP-002-01; no service or database required."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.domain.contracts import (
    allowed_transitions,
    fencing_rule,
    is_terminal,
    validate_transition,
)
from app.domain.errors import HTTP_STATUS_BY_CODE, DomainContractError, ErrorCode
from app.lifecycle import FENCING_RULES, TERMINAL_STATUSES, TRANSITIONS, WorkItemStatus

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize(("source", "target", "role"), TRANSITIONS)
def test_each_existing_transition_is_accepted(source: str, target: str, role: str) -> None:
    validate_transition(source, target, role, current_status=source)
    assert WorkItemStatus(target) in allowed_transitions(source, role)


@pytest.mark.parametrize("status", list(WorkItemStatus))
def test_all_eight_statuses_are_recognized(status: WorkItemStatus) -> None:
    assert is_terminal(status) == (status in TERMINAL_STATUSES)


@pytest.mark.parametrize("status", list(TERMINAL_STATUSES))
def test_terminal_status_has_no_outgoing_edge(status: WorkItemStatus) -> None:
    assert not any(source == status for source, _target, _role in TRANSITIONS)
    for role in ("worker", "work_item_editor", "result_acceptor", "assignment_authority"):
        assert allowed_transitions(status, role) == frozenset()


@pytest.mark.parametrize(
    ("source", "target", "role", "current", "code", "http"),
    [
        ("created", "done", "work_item_editor", None, ErrorCode.VALIDATION_ERROR, 400),
        ("done", "ready", "worker", None, ErrorCode.VALIDATION_ERROR, 400),
        ("unrecognized", "ready", "worker", None, ErrorCode.VALIDATION_ERROR, 400),
        ("created", "ready", "worker", None, ErrorCode.FORBIDDEN, 403),
        ("created", "ready", "work_item_editor", "claimed", ErrorCode.INVALID_STATE, 409),
    ],
)
def test_rejected_transition_has_stable_error(
    source: str,
    target: str,
    role: str,
    current: str | None,
    code: ErrorCode,
    http: int,
) -> None:
    with pytest.raises(DomainContractError) as exc:
        validate_transition(source, target, role, current_status=current)
    assert exc.value.code == code
    assert exc.value.http_status == http


def test_contract_is_derived_from_existing_lifecycle_and_documentation() -> None:
    assert len(WorkItemStatus) == 8
    assert len(TRANSITIONS) == 15
    assert len(set(TRANSITIONS)) == 15
    assert len(FENCING_RULES) == 6
    document = (ROOT / "docs/WORKITEM_LIFECYCLE.md").read_text(encoding="utf-8")
    assert _markdown_rows(document, "## Übergänge", 3) == set(TRANSITIONS)
    assert _markdown_rows(document, "## Fencing", 2) == set(FENCING_RULES)


@pytest.mark.parametrize(("operation", "rule"), FENCING_RULES)
def test_fencing_is_a_read_only_lookup(operation: str, rule: str) -> None:
    assert fencing_rule(operation) == rule


def test_unknown_fencing_operation_is_rejected() -> None:
    with pytest.raises(DomainContractError) as exc:
        fencing_rule("override")
    assert exc.value.code == ErrorCode.VALIDATION_ERROR


def test_openapi_v1_errors_statuses_and_paths_match() -> None:
    spec = yaml.safe_load((ROOT / "api/openapi.yaml").read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    assert set(schemas["WorkItemStatus"]["enum"]) == {status.value for status in WorkItemStatus}
    assert set(schemas["ErrorCode"]["enum"]) == {code.value for code in ErrorCode}
    assert set(HTTP_STATUS_BY_CODE) == set(ErrorCode)
    assert set(spec["paths"]) == {
        "/v1/work-items",
        "/v1/work-items/{work_item_id}",
        "/v1/work-items/{work_item_id}/transitions",
        "/v1/work-items/{work_item_id}/claims",
        "/v1/workers",
        "/v1/workers/{worker_id}",
        "/v1/workers/{worker_id}/heartbeat",
        "/v1/workers/{worker_id}/disable",
        "/v1/assignments/{assignment_id}",
        "/v1/assignments/{assignment_id}/renew",
        "/v1/assignments/{assignment_id}/release",
        "/v1/assignments/{assignment_id}/result",
        "/v1/audit-events",
    }
    for path_item in spec["paths"].values():
        for method, operation in path_item.items():
            if method in {"get", "post", "patch"}:
                assert operation["responses"]


def _markdown_rows(document: str, heading: str, width: int) -> set[tuple[str, ...]]:
    lines = document.splitlines()
    start = lines.index(heading)
    result: set[tuple[str, ...]] = set()
    for line in lines[start + 1 :]:
        if line.startswith("## ") or (result and not line.startswith("|")):
            break
        if not line.startswith("|"):
            continue
        cells = tuple(cell.strip().strip("`") for cell in line.strip("|").split("|"))
        if cells[0] and set(cells[0]) <= {"-", ":"}:
            continue
        if cells[0] not in {"from_status", "operation"}:
            result.add(cells[:width])
    return result
