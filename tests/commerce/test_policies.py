from uuid import uuid4
import pytest
from app.commerce.schemas import AuthorizedContext, DiagnosticFinding, DiagnosticRun, DiagnosticModule, Severity
from app.commerce.policies import PolicyDenied, require_tenant, require_tool, require_no_p0_downgrade

def test_unknown_tool_denied():
    with pytest.raises(PolicyDenied):
        require_tool("shop.publish")

def test_missing_role_denied():
    tenant = uuid4()
    ctx = AuthorizedContext(identity_id=uuid4(), tenant_id=tenant, roles=frozenset({"worker"}))
    with pytest.raises(PolicyDenied):
        require_tenant(ctx, tenant)

def test_p0_cannot_be_dropped():
    tenant, listing, finding = uuid4(), uuid4(), uuid4()
    item = DiagnosticFinding(finding_id=finding, module=DiagnosticModule.COMPLIANCE_CERTIFICATIONS,
        severity=Severity.P0, rule_id="SYNTHETIC", rule_version="1", evidence="synthetic")
    before = DiagnosticRun(run_id=uuid4(), listing_id=listing, tenant_id=tenant,
        rule_set_version="1", findings=(item,))
    after = before.model_copy(update={"findings": ()})
    with pytest.raises(PolicyDenied):
        require_no_p0_downgrade(before, after)
