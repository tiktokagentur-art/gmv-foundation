"""Isolated policy tests; no imports from other test modules."""

from uuid import UUID

import pytest

from app.management.policy import can_approve, permits
from app.management.schemas import AuthorizationContextV1, ManagerProfileV1

ID = UUID("00000000-0000-0000-0000-000000000001")
OTHER = UUID("00000000-0000-0000-0000-000000000002")


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


def context(**overrides):
    data = dict(
        identity_id=ID,
        identity_kind="worker",
        employee_id="GMV-VE-999",
        granted_scopes=frozenset({"management.read", "management.approve"}),
        mandate_version="test-v1",
        identity_verified=True,
        identity_blocked=False,
    )
    data.update(overrides)
    return AuthorizationContextV1(**data)


def test_allow_only_verified_matching_scope():
    assert permits(manager(), context(), "management.read")


@pytest.mark.parametrize(
    "profile,auth,scope",
    [
        ({"operating_status": "planned"}, {}, "management.read"),
        ({"profile_review_status": "pending"}, {}, "management.read"),
        ({"technical_access_status": "unverified"}, {}, "management.read"),
        ({}, {"identity_verified": False}, "management.read"),
        ({}, {"identity_blocked": True}, "management.read"),
        ({}, {"employee_id": "GMV-VE-998"}, "management.read"),
        ({}, {"mandate_version": "old"}, "management.read"),
        ({}, {"granted_scopes": frozenset()}, "management.read"),
        ({}, {}, "management.admin"),
        ({}, {}, "unrecognized.scope"),
    ],
)
def test_deny(profile, auth, scope):
    assert not permits(manager(**profile), context(**auth), scope)


def test_no_self_approval_or_conflicted_reviewer():
    assert not can_approve(manager(), context(), ID)
    assert not can_approve(manager(), context(), OTHER, reviewer_conflicted=True)
    assert can_approve(manager(), context(), OTHER)
