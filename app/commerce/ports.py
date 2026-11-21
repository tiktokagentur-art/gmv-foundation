"""Protocol boundaries; deliberately no production implementations."""
from __future__ import annotations
from typing import Protocol
from uuid import UUID
from app.commerce.schemas import AuthorizedContext, ChangeProposal, DiagnosticRun, ListingSnapshot

class ListingReader(Protocol):
    def get_listing(self, listing_id: UUID, context: AuthorizedContext) -> ListingSnapshot: ...

class DiagnosticPort(Protocol):
    def analyze(self, listing: ListingSnapshot, context: AuthorizedContext) -> DiagnosticRun: ...

class ProposalPort(Protocol):
    def draft(self, listing: ListingSnapshot, run: DiagnosticRun, context: AuthorizedContext) -> ChangeProposal: ...

class ControlPlanePort(Protocol):
    """Future external authority adapter; no local WorkItem state machine."""
    def submit_result(self, assignment_id: UUID, fencing_token: int, result: dict[str, object]) -> None: ...
