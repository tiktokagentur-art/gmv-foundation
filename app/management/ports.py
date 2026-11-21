"""Dependency-inversion ports; no I/O implementations or credentials."""
from __future__ import annotations
from typing import Protocol
from uuid import UUID
from app.management.schemas import ManagerProfileV1, ManagementDecisionV1

class ManagerRegistryPort(Protocol):
    def get_manager(self, manager_id: UUID) -> ManagerProfileV1 | None: ...

class MandatePolicyPort(Protocol):
    def permits(self, manager: ManagerProfileV1, context: object, scope: str) -> bool: ...

class WorkItemRequestPort(Protocol):
    def propose(self, decision: ManagementDecisionV1, idempotency_key: str) -> str: ...

class ManagementAuditPort(Protocol):
    def record(self, action: str, object_id: UUID, allowed: bool) -> None: ...
