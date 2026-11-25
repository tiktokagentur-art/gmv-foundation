"""Fail-closed local policy helpers, not an authentication provider."""
from __future__ import annotations
from uuid import UUID
from app.commerce.schemas import AuthorizedContext, DiagnosticRun, Severity

class PolicyDenied(PermissionError):
    pass

def require_tenant(context: AuthorizedContext, tenant_id: UUID, role: str = "commerce_reader") -> None:
    if not context.active or context.tenant_id != tenant_id or role not in context.roles:
        raise PolicyDenied("access denied")

def require_no_p0_downgrade(original: DiagnosticRun, proposed: DiagnosticRun) -> None:
    if original.listing_id != proposed.listing_id or original.tenant_id != proposed.tenant_id:
        raise PolicyDenied("diagnostic provenance mismatch")
    before = {f.finding_id: f for f in original.findings if f.severity == Severity.P0}
    after = {f.finding_id: f for f in proposed.findings}
    if any(fid not in after or after[fid].severity != Severity.P0 for fid in before):
        raise PolicyDenied("P0 finding must not be removed or downgraded")

ALLOWED_OFFLINE_TOOLS = frozenset({"listing.read", "diagnostic.analyze", "proposal.draft"})
def require_tool(tool_name: str) -> None:
    if tool_name not in ALLOWED_OFFLINE_TOOLS:
        raise PolicyDenied("tool not allowed")
