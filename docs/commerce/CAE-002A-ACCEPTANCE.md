# CAE-002A acceptance and limitations

## Required offline evidence

1. Ruff and Pytest succeed with no external provider or database.
2. Only the ten approved new files appear in the branch diff.
3. No edits to app/main.py, app/lifecycle.py, api/openapi.yaml, migrations or ADRs.
4. Schemas reject extra fields and unsupported versions.
5. Sixteen module names are represented; no claim of sixteen implemented rules.
6. Mock output is deterministic and explicitly partial.
7. Cross-tenant access, missing role, unknown tools and P0 removal are denied.
8. No secrets, external API calls, DB connections, payments, publishing or deploys.

## Explicitly out of scope

Production authentication, server-side approval, real Seller Health diagnostics,
WorkItem/Lease/Fencing enforcement, persistent idempotency, API routes,
model inference and real provider integration. These must not be presented as
implemented or verified in CAE-002A. Future integrations require separate review.

## Stop conditions

Unexpected existing files, changed branch permissions, unapproved dependencies,
non-green checks, or inability to prove diff scope => stop and report.
