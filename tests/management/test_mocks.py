from uuid import UUID
import pytest
from app.management.mocks import MockRegistry, MockWorkItemRequests, MockAudit
from app.management.schemas import ManagementDecisionV1
from tests.management.test_schemas import manager, ID

def test_registry_is_in_memory():
    registry=MockRegistry({ID:manager()})
    assert registry.get_manager(ID) is not None
    assert registry.get_manager(UUID("00000000-0000-0000-0000-000000000002")) is None

def test_idempotency_and_conflict():
    adapter=MockWorkItemRequests()
    d=ManagementDecisionV1(decision_id=ID,decision_type="synthetic",requested_by=ID,responsible_manager_id=ID,mandate_version="test-v1",resource_version=1)
    assert adapter.propose(d,"key")==adapter.propose(d,"key")
    with pytest.raises(ValueError):
        adapter.propose(d.model_copy(update={"decision_type":"other"}),"key")
    assert len(adapter.requests)==1

def test_audit_memory_only():
    audit=MockAudit()
    audit.record("test",ID,False)
    assert audit.events==[("test",ID,False)]
