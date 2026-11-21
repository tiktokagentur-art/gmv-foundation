# GMVGANG Factory governance — FE-003B

Status: offline proposal, subject to independent review. Accepted repository ADRs take precedence.

- Aline coordinates; the existing Assignment Authority alone controls claims, leases, fencing and WorkItem state.
- Deny by default. Mock policy decisions require a known worker identity, an active mandate, matching WorkItem scope, a valid lease indicator, an allowed action and an explicit nonproduction context. A mock indicator is not a substitute for production authentication.
- L2 is a future target only. Production deployments, payments, publishing, access changes, contracts, migrations and real API calls are never permitted by this package.
- The approving specialist must differ from the requester and executor and be authorized for the result's discipline. Strategic exceptions require CEO approval. A mock approval does not change WorkItem state.
- The planned Factory Registry on Railway PostgreSQL contains validated operational projections. Notion remains authoritative for organizational fields. Conflicts and stale source versions must fail closed.
- Reservations are mock-only, in memory, UTC day-bound, and idempotent per request ID. Currency is EUR. Production requires transactional, atomic persistent reservations, audit evidence and independently approved budget authority.
- No VE IDs are allocated here. Verify the authoritative register before future assignment; preserve existing identities.
- ADR-0009 remains Proposed in the repository. The CEO's Expand/Contract, roll-forward-only decision must be formally reconciled by Deniz and approved by the CEO before any domain migration.
- All production changes require separate explicit approval. This work grants none.
