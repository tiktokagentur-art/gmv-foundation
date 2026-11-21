# GMV Expert Network V1 — Implementation Plan

Status: Proposed. Tracking: #56. No production changes authorized.

## Objective
100 versioned expert capability profiles, five offline pilot profiles, and optional separately authorized key agents. Expert profiles are not virtual employees.

## System boundaries
- Existing Control Plane and Aline retain assignment/claim/lease/fencing authority. Expert router is a subordinate adapter, not a new work-item owner.
- Railway PostgreSQL is proposed system of record for mandates, executions, budget reservations and audit. Supabase handles explicitly authorized portal projections and authentication integration; ownership must be verified before implementation.
- GitHub versions non-secret schemas, policy and tests. Railway hosts only after separate deployment approval.
- Public repository: no credentials, customer data, sensitive operational details or production identifiers.

## Registry contract (proposed)
ExpertProfile: id, version, category, description, capability_tags, input_schema, output_schema, tool_allowlist, risk_class, evaluation_suite, execution_mode, status.
EmployeeAssignment: existing_ve_id, profile_id, authorized_scope, mandate_version, status.
Execution: work_item_id, profile_version, correlation_id, claim_token, status, token_usage, cost, evidence_refs.
BudgetReservation: budget_scope, request_id, reserved_amount, actual_amount, status; atomic reservation and settlement required.

## Pilot profiles
1. Sales psychology: analyze anonymized objections, advisory only.
2. Sales optimization: propose improvements to outreach and scripts.
3. E-commerce listing analysis: prioritize listing quality findings.
4. Expert coordination: route test requests without taking over Aline's authority.
5. AI quality assurance: score outputs against defined evaluation fixtures.

## Delivery gates
1. Inventory existing code, issues, registry, data models and tools; record overlaps.
2. Define schemas and validate 100 profile records with unique IDs.
3. Build offline router and deny-by-default authorization with no live tools.
4. Test atomic budget reservations, concurrency, timeouts, retries and audit.
5. Run five profile evaluations with synthetic data.
6. Produce security, quality and cost evidence; request CEO approval before merge/deploy.

## Constraints
No merges, deployments, database migrations, productive writes, external customer communication, secrets, or new VE identities without separate approval. All changes remain on a feature branch and draft PR.
