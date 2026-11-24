"""Pure checks over the existing WorkItem lifecycle contract.

app.lifecycle remains the sole source of status, transition and fencing rules.
These helpers neither authorize identities nor check leases/tokens against
persistent state. Only the future Control Plane authority may do that.
"""

from __future__ import annotations

from types import MappingProxyType

from app.domain.errors import DomainContractError, ErrorCode
from app.lifecycle import FENCING_RULES, TERMINAL_STATUSES, TRANSITIONS, WorkItemStatus

_STATUS_VALUES = frozenset(status.value for status in WorkItemStatus)
_TRANSITION_SET = frozenset(TRANSITIONS)
_TRANSITION_EDGES = frozenset((source, target) for source, target, _role in TRANSITIONS)
_FENCING_RULES = MappingProxyType(dict(FENCING_RULES))


def allowed_transitions(from_status: str, requested_by: str) -> frozenset[WorkItemStatus]:
    """Return contract edges for a role, not an authorization decision."""
    _require_status(from_status)
    return frozenset(
        WorkItemStatus(target)
        for source, target, role in _TRANSITION_SET
        if source == from_status and role == requested_by
    )


def validate_transition(
    from_status: str,
    to_status: str,
    requested_by: str,
    *,
    current_status: str | None = None,
) -> None:
    """Validate a proposed edge; optional current_status detects stale proposals.

    The caller must separately authenticate and authorize the role, and, for
    worker operations, enforce the active assignment, lease and fencing token.
    No state is read or changed here.
    """
    _require_status(from_status)
    _require_status(to_status)
    if current_status is not None:
        _require_status(current_status)
        if current_status != from_status:
            raise DomainContractError(
                ErrorCode.INVALID_STATE, "Der Antrag passt nicht zum aktuellen Status."
            )
    if (from_status, to_status) not in _TRANSITION_EDGES:
        raise DomainContractError(
            ErrorCode.VALIDATION_ERROR, "Unzulässiger WorkItem-Übergang."
        )
    if (from_status, to_status, requested_by) not in _TRANSITION_SET:
        raise DomainContractError(
            ErrorCode.FORBIDDEN, "Die Rolle darf diesen Übergang nicht beantragen."
        )


def is_terminal(status: str) -> bool:
    """Check terminal status without modifying any WorkItem."""
    _require_status(status)
    return WorkItemStatus(status) in TERMINAL_STATUSES


def fencing_rule(operation: str) -> str:
    """Look up a named rule; do not issue or validate fencing tokens."""
    try:
        return _FENCING_RULES[operation]
    except KeyError:
        raise DomainContractError(
            ErrorCode.VALIDATION_ERROR, "Unbekannte Fencing-Operation."
        ) from None


def _require_status(status: str) -> None:
    if status not in _STATUS_VALUES:
        raise DomainContractError(ErrorCode.VALIDATION_ERROR, "Unbekannter WorkItem-Status.")
