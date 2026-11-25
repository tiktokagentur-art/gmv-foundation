"""Deterministic in-memory mocks. Never use as a production authority."""
from __future__ import annotations
from uuid import UUID, uuid5, NAMESPACE_URL
from app.commerce.policies import PolicyDenied, require_tenant, require_tool
from app.commerce.schemas import (AuthorizedContext, ChangeProposal, DiagnosticFinding,
    DiagnosticModule, DiagnosticRun, ListingSnapshot, Severity)

class MockListingReader:
    def __init__(self, listings: tuple[ListingSnapshot, ...] = ()) -> None:
        self._listings = {item.listing_id: item for item in listings}
    def get_listing(self, listing_id: UUID, context: AuthorizedContext) -> ListingSnapshot:
        require_tool("listing.read")
        item = self._listings.get(listing_id)
        if item is None:
            raise KeyError("listing not found")
        require_tenant(context, item.tenant_id)
        return item

class MockDiagnosticAdapter:
    def analyze(self, listing: ListingSnapshot, context: AuthorizedContext) -> DiagnosticRun:
        require_tool("diagnostic.analyze")
        require_tenant(context, listing.tenant_id)
        findings: list[DiagnosticFinding] = []
        if len(listing.title.strip()) < 10:
            findings.append(DiagnosticFinding(
                finding_id=uuid5(NAMESPACE_URL, f"{listing.listing_id}:TITLE_LENGTH:v1"),
                module=DiagnosticModule.TITLE, severity=Severity.P1,
                rule_id="TITLE_LENGTH", rule_version="1",
                evidence="Synthetic title has fewer than 10 characters",
                suggested_change="Provide a more descriptive title", evidence_status="verified"))
        return DiagnosticRun(run_id=uuid5(NAMESPACE_URL, f"{listing.listing_id}:{listing.resource_version}:v1"),
            listing_id=listing.listing_id, tenant_id=listing.tenant_id,
            rule_set_version="offline-mock-1", findings=tuple(findings), status="partial")

class MockProposalAdapter:
    def draft(self, listing: ListingSnapshot, run: DiagnosticRun,
              context: AuthorizedContext) -> ChangeProposal:
        require_tool("proposal.draft")
        require_tenant(context, listing.tenant_id, "commerce_editor")
        if run.listing_id != listing.listing_id or run.tenant_id != listing.tenant_id:
            raise PolicyDenied("diagnostic provenance mismatch")
        return ChangeProposal(
            proposal_id=uuid5(NAMESPACE_URL, f"{listing.listing_id}:{listing.resource_version}:proposal"),
            listing_id=listing.listing_id, tenant_id=listing.tenant_id,
            listing_version=listing.resource_version,
            title_suggestion=f"{listing.title.strip()} - detailed description",
            source_finding_ids=tuple(f.finding_id for f in run.findings))
