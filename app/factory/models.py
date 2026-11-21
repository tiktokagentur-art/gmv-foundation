"""Offline, versioned Pydantic contracts; no persistence or API calls."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class FactoryRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    factory_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    organizational_owner_ve_id: str = Field(min_length=1)
    technical_owner_ve_id: str | None = None
    status: Literal["planned", "disabled", "active"] = "planned"
    mandate_reference: str | None = None
    policy_reference: str | None = None
    budget_policy_reference: str | None = None


class AgentProfile(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    ve_id: str | None = None
    display_name: str = Field(min_length=1)
    position: str = Field(min_length=1)
    factory_id: str = Field(min_length=1)
    manager_ve_id: str | None = None
    mandate_id: str | None = None
    identity_subject: str | None = None
    autonomy_level: Literal["L0", "L1", "L2"] = "L0"
    operating_status: Literal["planned", "disabled", "active"] = "planned"
    policy_version: str | None = None


class BudgetPolicy(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    currency: Literal["EUR"] = "EUR"
    pilot_total_limit_cents: Literal[2500] = 2500
    daily_limit_cents: Literal[1000] = 1000
    workitem_limit_cents: Literal[500] = 500
    reservation_required: Literal[True] = True
    hard_stop_enabled: Literal[True] = True


class ApprovalRecord(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    approval_id: str = Field(min_length=1)
    workitem_id: str = Field(min_length=1)
    requester_ve_id: str = Field(min_length=1)
    executor_ve_id: str = Field(min_length=1)
    reviewer_ve_id: str = Field(min_length=1)
    decision: Literal["approved", "rejected"]
    risk_class: Literal["low", "medium", "high", "strategic"] = "low"
    evidence_reference: str | None = None
    policy_version: str | None = None

    @model_validator(mode="after")
    def no_self_approval(self) -> "ApprovalRecord":
        if self.decision == "approved" and self.reviewer_ve_id in (
            self.requester_ve_id, self.executor_ve_id
        ):
            raise ValueError("independent reviewer required")
        return self
