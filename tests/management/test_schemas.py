"""Schema and transport-contract negative tests with synthetic data."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.management.schemas import (
    ManagementDecisionV1,
    ManagementEscalationV1,
    ManagerProfileV1,
)

ID = UUID("00000000-0000-0000-0000-000000000001")


def manager(**overrides):
    data = dict(
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
    data.update(overrides)
    return ManagerProfileV1(**data)


def test_valid_profile():
    assert manager().schema_version == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"employee_id": ""},
        {"resource_version": 0},
        {"schema_version": 2},
        {"unexpected": "x"},
        {"operating_status": "unknown"},
    ],
)
def test_reject_invalid_profile(changes):
    with pytest.raises(ValidationError):
        manager(**changes)


def test_decision_and_escalation():
    decision = ManagementDecisionV1(
        decision_id=ID,
        decision_type="synthetic",
        requested_by=ID,
        responsible_manager_id=ID,
        mandate_version="test-v1",
        resource_version=1,
    )
    assert decision.status == "proposed"
    escalation = ManagementEscalationV1(
        escalation_id=ID,
        decision_id=ID,
        severity="high",
        reason_code="test",
        raised_by=ID,
        resource_version=1,
    )
    assert escalation.status == "open"
