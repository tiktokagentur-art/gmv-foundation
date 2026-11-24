# GMVGANG OS – Master Specification V1

- Version: 1.0
- Decision date: 2026-11-24
- Status: strategic direction approved; technical specification submitted for review
- Scope: Phase 01 documentation and backlog preparation only
- Baseline: `3c585c7cf167ade171282a495b7b211284c15778`

## 1. Purpose

GMVGANG OS is a modular enterprise operating platform for humans and authorized AI workers. The first transformation is a controlled replacement of Notion. GMVGANG is the initial internal reference customer; commercial operation is a later, separately approved stage. Extend the existing Foundation rather than rebuilding it.

## 2. CEO decision traceability

| ID | Approved strategic direction | Requirement |
| --- | --- | --- |
| OS-D001 | GMVGANG OS | Integrated modular platform |
| OS-D002 | Hybrid data architecture | Git for versioned documents, PostgreSQL for structured state, S3-compatible files, unified knowledge API |
| OS-D003 | Digital workplace | CEO, department, human and AI employee workspaces |
| OS-D004 | Provider independence | Replaceable adapters, exportability, eventual self-hosting |
| OS-D005 | Autonomous corporate memory | Source-aware retrieval, history, knowledge graph, scoped employee and team memory |
| OS-D006 | Autonomous collaboration | Messaging, structured handoffs, briefings, decisions and escalation |
| OS-D007 | Zero trust | Individual identity, tenant isolation, task-scoped authorization, audit, limits, revocation |
| OS-D008 | Modular hybrid development | Own differentiating business logic; reuse proven components |
| OS-D009 | Parallel controlled transformation | Aline program coordination, Symphony execution, seven-day work packages, WIP max three active group projects |
| OS-D010 | Independent technology business | SaaS, enterprise, developer APIs, marketplaces, self-hosting and white-label options |

These are strategic decisions, not grants of technical permissions or release authority. Existing accepted ADRs remain effective until explicitly superseded. No implicit reactivation of historical policies.

## 3. Existing Foundation and reuse

The public Foundation has FastAPI, health/readiness, a PostgreSQL schema metadata migration, OpenAPI contracts, lifecycle rules and CI. Its domain API and production WorkItem schema are not established merely by these contracts. See [architecture](ARCHITECTURE.md), [data model](DATA_MODEL.md), [API specification](API_SPECIFICATION.md), [lifecycle](WORKITEM_LIFECYCLE.md) and [ADRs](adr/README.md).

Reuse pending work after review: Control Plane PR #63; Management Factory PR #61; Symphony #74 and PRs #66/#88; dispatcher #72/#44; Code Mode #53 and PRs #54/#55; UI PR #37 and #39; governance #68/#70/#80 and PR #86. An open PR, draft or pilot is not proof of deployed functionality. Reconcile existing Factory contracts before building new ones.

The repository is public under ADR-0013. Never place internal documents, identity records, customer information, private source identifiers, secrets, internal logs or Notion exports here. Public evidence must be sanitized. A private knowledge repository is proposed; provisioning is outside Phase 01.

## 4. Architecture and module boundaries

Start with a modular FastAPI core and explicit interfaces; extract services only for measured isolation, capacity or operational needs.

| Module | Responsibility |
| --- | --- |
| Control Plane | WorkItem state, assignment, claims, leases, fencing |
| Command Center | Executive decisions, approvals and read projections |
| Workforce Engine | Employee records, mandates, identity references, competence |
| Management Factory | Planning, prioritization, briefs and coordination |
| Factory Engine | Common contracts for department-specific operations |
| Knowledge Center | Handbook, playbooks, SOPs and document retrieval |
| Corporate Memory | Source-aware index, history, graph and scoped retrieval |
| Communication Center | Messages, handoffs, meetings and escalation |
| Operations Center | Projects, work queue and execution evidence |
| Governance Engine | Authorization, risk, policy, approvals, audit |
| Performance Center | Usage, cost and KPI evidence |
| Integration and Developer Platform | Adapters, tool gateway, versioned APIs and SDKs |

Experience layer calls authorized APIs; it never writes underlying state directly. Integration layer uses Symphony for execution coordination, Code Mode for governed tool calls, and versioned events. Aline prioritizes; the existing Control Plane Assignment Authority alone grants or revokes assignments. Symphony and GitHub are not additional runtime state owners.

## 5. Data ownership and proposed contracts

| Domain | Authoritative owner |
| --- | --- |
| Source and technical ADRs | Git repository |
| Engineering queue and PR evidence | GitHub |
| Handbook, SOP content, playbooks | Private knowledge Git repository |
| WorkItem status and assignment | Control Plane |
| Employee registry and mandates | Workforce Engine / PostgreSQL |
| Business decisions | Decision Registry, reusing #80 |
| Authorization and approvals | Governance Engine |
| Accepted domain events | Owning domain audit store |
| Messages | Communication Center |
| File content | Private object store; metadata in owning domain |
| Search and embeddings | Derived index only; never authority |
| Credentials | Approved secrets provider |

Proposed entities: Tenant, Department, Employee, Mandate, Document, DocumentVersion, SourceReference, Decision, Approval, AuditEvent, Message, Evidence, ProviderBinding. Existing WorkItem, Worker, Claim and Assignment contracts are reused. New records carry stable UUID, tenant context, owner, version, timestamps, lifecycle state and provenance as applicable. Tenant membership and scoped access are server-side checks, never inferred from request body alone.

Proposed interfaces (not implemented): versioned document read/list/search, decision read/proposal, employee read, message submit, provider capability queries. Mutation requests require explicit policy, idempotency keys and expected versions. Events include schema version, actor, tenant, correlation ID, resource version and source evidence. Use transactional outbox or equivalent only after architecture approval; consumers deduplicate and fail closed on unknown versions. No migration before ADR-0009 is accepted.

## 6. Security and governance

Default deny, separate human and workload identities, least privilege, task-scoped time-limited grants, enforceable revocation, budget hard limits and kill switch. Tenant isolation extends to DB queries, object keys, caches, embeddings, graph edges, retrieval and audit. Test negative cases, including cross-tenant search, stale grants, prompt injection in retrieved material, replay and duplicate claims. Retrieved text is untrusted data, not authorization.

Use established identity, secret management, sandbox and monitoring components. Keycloak, ZITADEL, Infisical, pgvector, MkDocs, OpenTelemetry, React/TypeScript and policy-as-code engines are candidates or prior preferences, not deployment approvals. Evaluate license, data residency, security, portability and cost before selection.

Reconcile ADR-0004 with Review Governance V2 and #68/#86 before changes to merge authority. Resolve #70 before any autonomous release corridor. ADRs 0006–0011 require explicit decisions on backup/recovery, secrets, authentication, migrations, SLOs and release authority. ADR-0012 hosting region requires a data protection assessment before personal data transfer. No self-approval, bypass or automatic production merge authorization follows from this specification.

## 7. Knowledge transformation

Keep four knowledge areas: governance and handbook; departments and Factories; workforce references; processes and SOPs. Preserve historical archive separately. Reuse #81–#85, #77 and #80; no parallel knowledge registry or bidirectional status replication.

1. Inventory source objects, relations, versions, attachments, permissions, owners, archive status and access gaps.
2. Design encrypted export and manifest with checksums; test restoration.
3. Map each source ID to a target or an explicitly approved exclusion. Historical policy stays historical; conflicting decisions escalate.
4. Transform synthetic fixtures to Markdown, structured records and object references. Verify referential integrity, permissions and content.
5. After separate approval, stage a bounded real-data pilot in private targets and compare source/target readback.
6. Validate shadow operation, agent retrieval, links, document history, restore and rollback.
7. Obtain explicit cutover approval; freeze legacy writes, reconcile final delta and switch authority once.
8. Preserve read-only access and retention until separate decommissioning approval.

Exit targets: 100% classified in documented access scope; 100% mandatory documents and relations reconciled; 12/12 department mappings; 100% required links and owners; zero unresolved critical conflicts or access-control failures; verified restore and cutover rollback. UNKNOWN is not PASS.

## 8. Development plan and duplicate handling

The OS IDs below are requirement references, not automatically new tickets. Reuse existing issues or PRs; create only absent deliverables. All implementation is HOLD pending valid assignment, explicit isolated scope and applicable approvals.

| Requirement | Priority | Delivery / dependency |
| --- | --- | --- |
| GMV-OS-0001 Master specification | P0 | This documentation branch |
| GMV-OS-0002 Architecture reconciliation | P0 | New planning work; #70, #74, #80, PR #63/#86 |
| GMV-OS-0003 Tenant and domain contracts | P0 | Isolated contract work; ADR-0008/0009 and PR #63 |
| GMV-OS-0004 Private knowledge repository design | P0 | #82 plus knowledge foundation package |
| GMV-OS-0005 Knowledge API | P0 | Knowledge foundation package; tenant contracts |
| GMV-OS-0006 Secure migration pipeline | P0 | #81/#83; synthetic fixtures only |
| GMV-OS-0007 Knowledge Center MVP | P0 | Knowledge foundation package |
| GMV-OS-0008 Notion exit validation | P0 | #85; CEO cutover gate |
| GMV-OS-0009 Command Center | P1 | PR #37/#39; reuse offline UI |
| GMV-OS-0010 Workforce registry | P1 | Workforce contracts package; PR #63/#61 |
| GMV-OS-0011 Corporate Memory | P1 | Memory package; knowledge API and tenant contracts |
| GMV-OS-0012 Communication Center | P1 | Collaboration package; identity and #80 |
| GMV-OS-0013 Decision Registry | P1 | #80 |
| GMV-OS-0014 Department workspaces | P1 | #82 and existing UI/Factory contracts |
| GMV-OS-0015 Performance Center | P1 | #49; usage and KPI evidence |
| GMV-OS-0016 Operations Center | P1 | #74/#72/PR #63 |
| GMV-OS-0017 Provider independence | P2 | Provider adapter design; #53/#74 |
| GMV-OS-0018 SaaS operations | P2 | Commercial package; isolation evidence |
| GMV-OS-0019 Developer APIs and SDKs | P2 | Commercial package; #75 |
| GMV-OS-0020 Subscription and usage billing | P2 | Commercial package; no real billing |
| GMV-OS-0021 Enterprise administration | P2 | Commercial package |
| GMV-OS-0022 Employee marketplace | P3 | Future discovery |
| GMV-OS-0023 Factory marketplace | P3 | Future discovery |
| GMV-OS-0024 Self-hosting and white label | P3 | Future discovery |

Projects: Secure Foundation (reuse #68/#70/#74); Knowledge Infrastructure (reuse #81–#85); OS Foundation (architecture and domain contracts). Do not activate new projects before WIP availability. Each seven-day package has a bounded outcome, dependency checks, scoped paths, evidence and review. First sprint target: specification, synthetic knowledge retrieval/import and protected offline wiki prototype, not actual Notion shutdown.

## 9. Codex handoff and acceptance

Prepare separate isolated packages, not autonomous dispatch. Before implementation: pin base/head, inspect full diff and existing PRs, reserve exact allowed paths, verify valid assignment and explicit scope, stop on drift or collision.

- Architecture package: documents only; ownership and ADR conflict matrix.
- Tenant package: proposed schemas and synthetic tests; no database migrations.
- Knowledge package: mocked document adapter, offline search/API and wiki concept; no live connectors or provisioning.
- Migration package: deterministic synthetic manifest and import validation; no real data.
- Later packages: workforce, memory and collaboration mocks after dependency acceptance.

Every package must deliver reproducible positive/negative tests, exact head and changed-file list, CI results, limitations, evidence and rollback instructions. Existing CI, Codex technical review and risk-appropriate independent acceptance remain required. VERIFIED_DOCUMENTED requires actual execution, readback and canonical evidence. No fabricated success.

## 10. Activation boundaries and roadmap

Phase 01 permits only public-safe documentation, duplicate checks, backlog amendments, necessary issue creation and preparation of isolated Codex packages. No actual Codex assignment or activation, merge, deployment, production write, database migration, paid service, IAM change, Notion shutdown or automation reconfiguration.

Later gates: secure Foundation and knowledge prototype; approved private migration; internal operational proof; commercial readiness (security, privacy, licenses, isolation, support and cost); then marketplace and self-hosting. Existing automations remain until replacement is proven and separately approved.

Phase 01 rollback: close the unmerged documentation PR if needed; restore issue bodies from history; close only newly created planning tickets by authorized decision. No production rollback should be necessary.
