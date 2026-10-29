"""Strict analysis contracts shared by providers and the application service."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

FindingStatus = Literal["confirmed", "mentioned", "not_found", "conflicting"]
Priority = Literal["required", "preferred"]


class CriterionSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, from_attributes=True)

    id: int = Field(gt=0)
    vacancy_id: int = Field(gt=0)
    description: str = Field(min_length=1)
    priority: Priority
    active: bool
    display_order: int = Field(ge=0)
    updated_at: datetime

    @model_validator(mode="after")
    def nonblank_description(self) -> "CriterionSnapshot":
        if not self.description.strip():
            raise ValueError("Criterion description cannot be blank")
        return self


class CriterionFinding(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    criterion_id: int = Field(gt=0)
    status: FindingStatus
    evidence_quote: str | None
    evidence_page: int | None = Field(ge=1)
    follow_up_question: str | None

    @model_validator(mode="after")
    def evidence_matches_status(self) -> "CriterionFinding":
        if self.status == "not_found":
            if self.evidence_quote is not None or self.evidence_page is not None:
                raise ValueError("not_found cannot have evidence")
        elif self.evidence_quote is None or not self.evidence_quote.strip():
            raise ValueError("Evidence quote is required for this status")
        return self


class LLMAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    findings: list[CriterionFinding]


class SourcePage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    page: int = Field(ge=1)
    text: str
