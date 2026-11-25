# APR-005A: Offline PR Risk & Review Contracts

Status: implementation candidate; no production activation.

## Scope

Only ten newly added files on `feat/apr-005a-risk-review-mocks`. No external
API, GitHub merge, repository settings, permissions, Railway changes, migration,
CI workflow modification, or production approval.

## Contracts

- Strict immutable Pydantic v2 models, schema_version=1; unknown fields rejected.
- R0: explicitly scoped Markdown guides/tutorials (candidate only).
- R1: isolated fixture/mock paths (candidate only).
- R2: other Markdown docs.
- R3: application, governance, CI, security, dependency and deletion changes.
- R4: unknown or malformed paths; fail closed.
- Mixed changes inherit the highest risk.
- Every review binds to a 40-character head commit SHA and distinct reviewer ID.
- Synthetic review is never a formal GitHub approval.
- Required CI names: Lint and structure, Backend, Image.
- Deployment separation must be independently verified.
- All offline gate decisions are DENY by construction, including nominal cases.
  No production merge operator is implemented.

## Acceptance

Run Ruff and Pytest; inspect full 10-file diff. Ensure no existing files changed.
Check path traversal, mixed risk, stale SHA, self-review, absent checks,
deployment coupling and synthetic evidence. No merge or deployment.

## Remaining prerequisites

CEO-approved categories, verified GitHub identities, enforceable independent
GitHub approval, ruleset updates, Railway deployment decoupling and a separate
production authorization. None is granted by this change.
