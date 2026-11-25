"""Deterministic in-memory adapters; no network, database, secrets or worker calls."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.management.policy import permits
from app.management.schemas import (
    AuthorizationContextV1,
    ManagementDecisionV1,
    ManagerProfileV1,
)


@dataclass
class MockRegistry:
    managers: dict[UUID, ManagerProfileV1] = field(default_factory=dict)

    def get_manager(self, manager_id: UUID) -> ManagerProfileV1 | None:
        return self.managers.get(manager_id)


@dataclass
class MockMandatePolicy:
    def permits(
        self, manager: ManagerProfileV1, context: AuthorizationContextV1, scope: str
    ) -> bool:
        return permits(manager, context, scope)


@dataclass
class MockWorkItemRequests:
    requests: dict[str, tuple[ManagementDecisionV1, str]] = field(default_factory=dict)

    def propose(self, decision: ManagementDecisionV1, idempotency_key: str) -> str:
        if not idempotency_key or not idempotency_key.strip():
            raise ValueError("idempotency key required")
        existing = self.requests.get(idempotency_key)
        if existing is not None:
            if existing[0] != decision:
                raise ValueError("idempotency key conflict")
            return existing[1]
        reference = f"mock-request-{len(self.requests) + 1}"
        self.requests[idempotency_key] = (decision, reference)
        return reference


@dataclass
class MockAudit:
    events: list[tuple[str, UUID, bool]] = field(default_factory=list)

    def record(self, action: str, object_id: UUID, allowed: bool) -> None:
        self.events.append((action, object_id, allowed))
