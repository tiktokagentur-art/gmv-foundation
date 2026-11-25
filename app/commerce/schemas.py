"""Versioned, strict commerce contracts. No persistence or network access."""
from __future__ import annotations
from enum import StrEnum
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator

class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class Severity(StrEnum):
    P0 = "P0"
    P1 = "P1"
    P2 = "P2"

class DiagnosticModule(StrEnum):
    TITLE = "Title"
    IMAGES = "Images"
    ATTRIBUTES = "Attributes"
    PROHIBITED_WORDS = "Prohibited Words & Compliance"
    PRICING = "Pricing"
    SKU = "SKU"
    DESCRIPTION = "Description"
    VIDEO = "Video"
    CATEGORY = "Category"
    SEO = "SEO"
    VARIATIONS = "Variations"
    INVENTORY = "Inventory"
    SHIPPING = "Shipping"
    REVIEWS = "Reviews"
    PROMOTIONS = "Promotions"
    COMPLIANCE_CERTIFICATIONS = "Compliance & Certifications"

class AuthorizedContext(StrictModel):
    identity_id: UUID
    tenant_id: UUID
    roles: frozenset[str] = Field(min_length=1)
    active: bool = True

class ListingSnapshot(StrictModel):
    schema_version: Literal[1] = 1
    listing_id: UUID
    tenant_id: UUID
    resource_version: int = Field(ge=1)
    market: str = Field(min_length=2, max_length=8)
    platform: str = Field(min_length=1, max_length=64)
    title: str = Field(max_length=512)
    description: str = Field(max_length=20000)
    attributes: dict[str, str] = Field(default_factory=dict)

class DiagnosticFinding(StrictModel):
    schema_version: Literal[1] = 1
    finding_id: UUID
    module: DiagnosticModule
    severity: Severity
    rule_id: str = Field(min_length=1, max_length=128)
    rule_version: str = Field(min_length=1, max_length=64)
    evidence: str = Field(min_length=1, max_length=4000)
    suggested_change: str | None = None
    evidence_status: Literal["verified", "uncertain", "missing"] = "uncertain"

class DiagnosticRun(StrictModel):
    schema_version: Literal[1] = 1
    run_id: UUID
    listing_id: UUID
    tenant_id: UUID
    rule_set_version: str = Field(min_length=1)
    findings: tuple[DiagnosticFinding, ...] = ()
    status: Literal["completed", "partial", "failed"] = "completed"

class ChangeProposal(StrictModel):
    schema_version: Literal[1] = 1
    proposal_id: UUID
    listing_id: UUID
    tenant_id: UUID
    listing_version: int = Field(ge=1)
    title_suggestion: str | None = None
    description_suggestion: str | None = None
    source_finding_ids: tuple[UUID, ...] = ()
    status: Literal["draft"] = "draft"
    @model_validator(mode="after")
    def has_change(self) -> "ChangeProposal":
        if self.title_suggestion is None and self.description_suggestion is None:
            raise ValueError("proposal requires at least one suggested change")
        return self
