from uuid import UUID
from app.management.schemas import AuthorizationContextV1
from app.management.policy import permits, can_approve
from tests.management.test_schemas import manager, ID

OTHER=UUID("00000000-0000-0000-0000-000000000002")

def context(**overrides):
    data=dict(identity_id=ID,identity_kind="worker",employee_id="GMV-VE-999",granted_scopes=frozenset({"management.read","management.approve"}),mandate_version="test-v1",identity_verified=True,identity_blocked=False)
    data.update(overrides)
    return AuthorizationContextV1(**data)

def test_allow_only_verified_matching_scope():
    assert permits(manager(),context(),"management.read")

import pytest
@pytest.mark.parametrize("profile,auth,scope",[
    ({"operating_status":"planned"},{},"management.read"),
    ({"profile_review_status":"pending"},{},"management.read"),
    ({"technical_access_status":"unverified"},{},"management.read"),
    ({},{"identity_verified":False},"management.read"),
    ({},{"identity_blocked":True},"management.read"),
    ({},{"employee_id":"GMV-VE-998"},"management.read"),
    ({},{"mandate_version":"old"},"management.read"),
    ({},{"granted_scopes":frozenset()},"management.read"),
    ({},{},"management.admin"),
])
def test_deny(profile,auth,scope):
    assert not permits(manager(**profile),context(**auth),scope)

def test_no_self_approval():
    assert not can_approve(manager(),context(),ID)
    assert can_approve(manager(),context(),OTHER)
