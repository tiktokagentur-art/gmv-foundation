"""WorkItem lifecycle contract.

This module is the machine-readable state machine for the V1 contract.
It does not implement HTTP endpoints or persistence.
"""

from __future__ import annotations

from enum import StrEnum


class WorkItemStatus(StrEnum):
    CREATED = "created"
    READY = "ready"
    CLAIMED = "claimed"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


TERMINAL_STATUSES = frozenset(
    {
        WorkItemStatus.DONE,
        WorkItemStatus.FAILED,
        WorkItemStatus.CANCELLED,
    }
)

# (from_status, to_status, requested_by)
# The Control Plane is the only writer. requested_by is who may ask.
TRANSITIONS: tuple[tuple[str, str, str], ...] = (
    ("created", "ready", "work_item_editor"),
    ("created", "cancelled", "work_item_editor"),
    ("ready", "claimed", "worker"),
    ("ready", "cancelled", "work_item_editor"),
    ("claimed", "in_progress", "worker"),
    ("claimed", "ready", "worker"),
    ("claimed", "ready", "assignment_authority"),
    ("claimed", "cancelled", "work_item_editor"),
    ("in_progress", "submitted", "worker"),
    ("in_progress", "failed", "worker"),
    ("in_progress", "ready", "assignment_authority"),
    ("in_progress", "cancelled", "work_item_editor"),
    ("submitted", "done", "result_acceptor"),
    ("submitted", "failed", "result_acceptor"),
    ("submitted", "cancelled", "work_item_editor"),
)

# rule is the contract word used in docs/WORKITEM_LIFECYCLE.md
FENCING_RULES: tuple[tuple[str, str], ...] = (
    ("claim", "issued"),
    ("renew", "required"),
    ("release", "required"),
    ("start", "required"),
    ("result", "required"),
    ("lease_expiry", "invalidated"),
)
