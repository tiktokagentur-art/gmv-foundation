# GMV Code Mode Gateway V1 — initial scaffold

Tracking: #53. Status: experimental, not deployed.

## Scope
The initial Python module is a **policy-only scaffold**, not a running service.
It does not call GitHub, execute generated code, expose routes, or load credentials.
The grant mapping in unit tests is synthetic and does not provision real permissions.

## Safety boundaries
- Deny unknown tools, actors, and ungranted capabilities.
- Require an explicit approval signal for write-classified tools.
- A caller-supplied boolean is **not** sufficient production approval evidence.
  Before enabling writes, implement signed, short-lived, actor- and action-bound
  approval tokens, trusted identity verification, and immutable audit records.
- Never execute untrusted code inside the FastAPI application process.
- Implement future code execution in a separate sandboxed worker with strict
  resource limits, network egress controls, and no default secret mounts.
- No secrets, API keys, hostnames, or private infrastructure metadata in this
  public repository.
- Aline remains the sole assignment authority; this gateway does not own
  WorkItem claims, leases, or state.

## Next increments
1. Add structured tool schemas, validated parameters, and redacted audit events.
2. Add verified workload identity and policy persistence.
3. Add read-only GitHub adapter for Aline behind authenticated gateway endpoint.
4. Add sandbox executor, budgets, deadlines, and per-tool quotas.
5. Integrate Software Factory Issue-to-Draft-PR workflow with explicit approvals.

## Acceptance
Run `pytest tests/test_codemode_gateway.py` and existing CI. Draft PR only;
no merge or deployment without CEO approval.
