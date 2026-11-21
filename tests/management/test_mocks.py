"""Isolated in-memory adapter tests with synthetic IDs."""

from uuid import UUID

import pytest

from app.management.mocks import MockAudit, MockRegistry, MockWorkItemRequests
from app.management.schemas import ManagementDecisionV1, ManagerProfileV1

ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER = UUID("00000000-0000-0000-0000-000000000002")


def manager():
    return ManagerProfileV1(
        manager_id=ID,
        employee_id="GMV-VE-999",
        department_id="synthetic",
        reports_to="CEO",
        mandate_version="test-v1",
        operating_status="active",
        profile_review_status="verified",
        technical_access_status="verified",
        resource_version=1,
    )


def test_registry_is_in_memory():
    registry = MockRegistry({ID: manager()})
    assert registry.get_manager(ID) is not None
    assert registry.get_manager(OTHER) is None


def test_idempotency_and_conflict():
    adapter = MockWorkItemRequests()
    decision = ManagementDecisionV1(
        decision_id=ID,
        decision_type="synthetic",
        requested_by=ID,
        responsible_manager_id=ID,
        mandate_version="test-v1",
        resource_version=1,
    )
    assert adapter.propose(decision, "key") == adapter.propose(decision, "key")
    with pytest.raises(ValueError):
        adapter.propose(decision.model_copy(update={"decision_type": "other"}), "key")
    with pytest.raises(ValueError):
        adapter.propose(decision, " ")
    assert len(adapter.requests) == 1


def test_audit_memory_only():
    audit = MockAudit()
    audit.record("test", ID, False)
    assert audit.events == [("test", ID, False)]
