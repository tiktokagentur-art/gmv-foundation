"""Fail-closed, deterministic mock-only policy. Not production authentication."""
from __future__ import annotations

from dataclasses import dataclass

MOCK_ACTIONS = frozenset({"analyze_mock", "research_mock", "draft_mock", "test_mock"})
BLOCKED_ACTIONS = frozenset(
    {
        "deploy",
        "publish",
        "pay",
        "migrate",
        "change_permissions",
        "external_api",
        "activate_agent",
    }
)


@dataclass(frozen=True)
class MockPolicyRequest:
    worker_identity: str
    mandate_id: str
    workitem_id: str
    action: str
    allowed_actions: frozenset[str]
    authorized_workitem_id: str
    lease_valid: bool
    mandate_active: bool
    isolated: bool


def evaluate_action(request: MockPolicyRequest) -> bool:
    return bool(
        request.worker_identity
        and request.mandate_id
        and request.workitem_id
        and request.mandate_active
        and request.lease_valid
        and request.isolated
        and request.workitem_id == request.authorized_workitem_id
        and request.action in MOCK_ACTIONS
        and request.action not in BLOCKED_ACTIONS
        and request.action in request.allowed_actions
    )
