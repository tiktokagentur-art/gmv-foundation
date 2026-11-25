# CAE-002A – Commerce contracts (offline only)

## Scope

Only versioned Pydantic contracts, protocols and in-memory mocks. No API routes,
real provider adapters, authentication issuer, database schema or Control Plane runtime.
This package is **not** a production security boundary. Its AuthorizedContext is
assumed to have been established by a future trusted server-side authenticator.

## Ownership

- WorkItem, Assignment, Claim, Lease, Fencing, Worker and their accepted audit events:
  **existing Control Plane only**, per ADR-0003 and DATA_MODEL.md.
- ListingSnapshot, DiagnosticRun, DiagnosticFinding and ChangeProposal:
  **Commerce domain**, modeled here only in memory. No persistence authority yet.
- Model Gateway and Code Mode Gateway: **external shared services**, not duplicated here.

## Versioning

All transport-ready models have schema_version=1. Unknown request fields and
unknown schema versions are rejected. New required fields or semantic changes
require a new major schema version; additive optional fields may be considered
within the same version. UUIDs identify entities; resource_version starts at 1.

## Limits

The mock diagnostic intentionally checks only a synthetic Title length rule;
its status is partial and **does not represent the 16-module Seller Health Check**.
All 16 module identifiers exist in the contract for future integration with #40.
No publishing, checkout, pricing, stock, live APIs or production approval.

## Governance

ADR-0009 is CEO-approved in planning but Proposed in the repository and
scripts/validate_structure.py. No ADR modification or migration in CAE-002A.
ADR-0008 and GF-008 identity implementation remain prerequisites for live use.
