from uuid import uuid4
import pytest
from app.commerce.schemas import AuthorizedContext, ListingSnapshot
from app.commerce.mock_adapters import MockListingReader, MockDiagnosticAdapter, MockProposalAdapter
from app.commerce.policies import PolicyDenied

def sample():
    tenant = uuid4()
    listing = ListingSnapshot(listing_id=uuid4(), tenant_id=tenant, resource_version=1,
                              market="DE", platform="mock", title="Short", description="synthetic")
    ctx = AuthorizedContext(identity_id=uuid4(), tenant_id=tenant,
                            roles=frozenset({"commerce_reader", "commerce_editor"}))
    return listing, ctx

def test_offline_deterministic_flow():
    listing, ctx = sample()
    reader = MockListingReader((listing,))
    result = MockDiagnosticAdapter().analyze(reader.get_listing(listing.listing_id, ctx), ctx)
    assert result.status == "partial"  # only synthetic Title rule; never claim all 16 checked
    assert result.findings[0].severity == "P1"
    assert result == MockDiagnosticAdapter().analyze(listing, ctx)
    proposal = MockProposalAdapter().draft(listing, result, ctx)
    assert proposal.status == "draft"

def test_cross_tenant_denied():
    listing, ctx = sample()
    outsider = ctx.model_copy(update={"tenant_id": uuid4()})
    with pytest.raises(PolicyDenied):
        MockListingReader((listing,)).get_listing(listing.listing_id, outsider)
    with pytest.raises(PolicyDenied):
        MockDiagnosticAdapter().analyze(listing, outsider)
