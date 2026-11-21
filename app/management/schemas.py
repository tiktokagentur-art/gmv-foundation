"""Versioned, strictly validated Management Factory contracts (offline only)."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class OperatingStatus(StrEnum):
    PLANNED="planned"
    ACTIVE="active"
    PAUSED="paused"
    ARCHIVED="archived"

class ReviewStatus(StrEnum):
    PENDING="pending"
    VERIFIED="verified"
    FAILED="failed"

class AccessStatus(StrEnum):
    UNVERIFIED="unverified"
    VERIFIED="verified"
    BLOCKED="blocked"

class DecisionStatus(StrEnum):
    PROPOSED="proposed"
    UNDER_REVIEW="under_review"
    APPROVED="approved"
    REJECTED="rejected"

class EscalationStatus(StrEnum):
    OPEN="open"
    UNDER_REVIEW="under_review"
    RESOLVED="resolved"

class Severity(StrEnum):
    LOW="low"
    MEDIUM="medium"
    HIGH="high"
    CRITICAL="critical"

class IdentityKind(StrEnum):
    HUMAN="human"
    SERVICE="service"
    WORKER="worker"

class ManagerProfileV1(StrictModel):
    schema_version: Literal[1]=1
    manager_id: UUID
    employee_id: str=Field(pattern=r"^GMV-VE-[0-9]{3,}$")
    department_id: str=Field(min_length=1)
    reports_to: str=Field(min_length=1)
    mandate_version: str=Field(min_length=1)
    operating_status: OperatingStatus
    profile_review_status: ReviewStatus
    technical_access_status: AccessStatus
    resource_version: int=Field(ge=1)

class ManagementDecisionV1(StrictModel):
    schema_version: Literal[1]=1
    decision_id: UUID
    decision_type: str=Field(min_length=1)
    requested_by: UUID
    responsible_manager_id: UUID
    mandate_version: str=Field(min_length=1)
    status: DecisionStatus=DecisionStatus.PROPOSED
    resource_version: int=Field(ge=1)

class ManagementEscalationV1(StrictModel):
    schema_version: Literal[1]=1
    escalation_id: UUID
    decision_id: UUID
    severity: Severity
    reason_code: str=Field(min_length=1)
    raised_by: UUID
    status: EscalationStatus=EscalationStatus.OPEN
    resource_version: int=Field(ge=1)

class AuthorizationContextV1(StrictModel):
    schema_version: Literal[1]=1
    identity_id: UUID
    identity_kind: IdentityKind
    employee_id: str=Field(pattern=r"^GMV-VE-[0-9]{3,}$")
    granted_scopes: frozenset[str]=Field(default_factory=frozenset)
    mandate_version: str=Field(min_length=1)
    identity_verified: bool=False
    identity_blocked: bool=True
    @field_validator("granted_scopes")
    @classmethod
    def valid_scopes(cls, value: frozenset[str]) -> frozenset[str]:
        if any(not scope or scope.strip()!=scope for scope in value):
            raise ValueError("invalid scope")
        return value
