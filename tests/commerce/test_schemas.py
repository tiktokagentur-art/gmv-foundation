from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.commerce.schemas import ListingSnapshot, DiagnosticFinding, DiagnosticModule, Severity, ChangeProposal

def test_all_16_modules():
    assert len(DiagnosticModule) == 16

def test_schema_rejects_unknown_fields_and_versions():
    data = dict(listing_id=uuid4(), tenant_id=uuid4(), resource_version=1,
                market="DE", platform="generic", title="example", description="text")
    with pytest.raises(ValidationError):
        ListingSnapshot(**data, unexpected=True)
    with pytest.raises(ValidationError):
        ListingSnapshot(**data, schema_version=2)

def test_proposal_requires_change():
    with pytest.raises(ValidationError):
        ChangeProposal(proposal_id=uuid4(), listing_id=uuid4(), tenant_id=uuid4(), listing_version=1)

def test_finding_severity():
    item = DiagnosticFinding(finding_id=uuid4(), module=DiagnosticModule.TITLE,
                             severity=Severity.P0, rule_id="X", rule_version="1", evidence="synthetic")
    assert item.severity == Severity.P0
