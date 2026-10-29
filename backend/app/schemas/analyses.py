"""HTTP contracts for S04 runs and validated results."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from backend.app.llm.contracts import CriterionSnapshot, FindingStatus

RunStatus = Literal["pending", "running", "completed", "completed_with_errors", "failed", "interrupted"]
DocumentStatus = Literal["pending", "running", "completed", "failed", "interrupted"]


class RunRead(BaseModel):
    id: int
    vacancy_id: int
    status: RunStatus
    provider: str
    model: str | None
    schema_version: str
    prompt_version: str
    criterion_snapshot: list[CriterionSnapshot]
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    total: int = Field(ge=0)
    pending: int = Field(ge=0)
    running: int = Field(ge=0)
    completed: int = Field(ge=0)
    failed: int = Field(ge=0)
    interrupted: int = Field(ge=0)


class FindingRead(BaseModel):
    criterion_id: int
    status: FindingStatus
    evidence_quote: str | None
    evidence_page: int | None
    follow_up_question: str | None


class DocumentRead(BaseModel):
    resume_id: int
    filename: str
    status: DocumentStatus
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    findings: list[FindingRead]


class ResultsRead(BaseModel):
    run_id: int
    results: list[DocumentRead]
