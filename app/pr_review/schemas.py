"""Versioned, immutable offline review inputs and outputs."""
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Risk(StrEnum):
    R0 = "R0"
    R1 = "R1"
    R2 = "R2"
    R3 = "R3"
    R4 = "R4"


class Verdict(StrEnum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class Change(StrictModel):
    path: str = Field(min_length=1)
    status: str = Field(pattern="^(added|modified|removed|renamed)$")


class ReviewRequest(StrictModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    pr_number: int = Field(gt=0)
    head_sha: str = Field(pattern="^[0-9a-f]{40}$")
    author_id: str = Field(min_length=1)
    changes: tuple[Change, ...] = Field(min_length=1)


class ReviewEvidence(StrictModel):
    schema_version: int = Field(default=1, ge=1, le=1)
    head_sha: str = Field(pattern="^[0-9a-f]{40}$")
    reviewer_id: str = Field(min_length=1)
    author_id: str = Field(min_length=1)
    approved: bool
    independent: bool
    synthetic: bool = True


class GateInputs(StrictModel):
    request: ReviewRequest
    evidence: ReviewEvidence | None = None
    passed_checks: frozenset[str] = frozenset()
    deployment_separated: bool = False
    category_approved: bool = False


class GateDecision(StrictModel):
    schema_version: int = 1
    verdict: Verdict
    risk: Risk
    reasons: tuple[str, ...]
    simulated: bool = True
