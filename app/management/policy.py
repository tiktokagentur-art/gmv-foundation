"""Pure, fail-closed offline policy; not a real authentication implementation."""

from __future__ import annotations

from uuid import UUID

from app.management.schemas import (
    AccessStatus,
    AuthorizationContextV1,
    ManagerProfileV1,
    OperatingStatus,
    ReviewStatus,
)

MANAGEMENT_SCOPES = frozenset(
    {
        "management.read",
        "management.propose",
        "management.review",
        "management.approve",
        "management.escalate",
        "management.metrics.read",
        "management.admin",
    }
)


def permits(manager: ManagerProfileV1, context: AuthorizationContextV1, scope: str) -> bool:
    if scope not in MANAGEMENT_SCOPES or scope not in context.granted_scopes:
        return False
    if not context.identity_verified or context.identity_blocked:
        return False
    if manager.operating_status is not OperatingStatus.ACTIVE:
        return False
    if manager.profile_review_status is not ReviewStatus.VERIFIED:
        return False
    if manager.technical_access_status is not AccessStatus.VERIFIED:
        return False
    if manager.employee_id != context.employee_id:
        return False
    return manager.mandate_version == context.mandate_version


def can_approve(
    manager: ManagerProfileV1,
    context: AuthorizationContextV1,
    requester_identity_id: UUID,
    *,
    reviewer_conflicted: bool = False,
) -> bool:
    """Deny self-approval or declared conflicts; actual reviewer checks remain upstream."""
    if reviewer_conflicted or context.identity_id == requester_identity_id:
        return False
    return permits(manager, context, "management.approve")
