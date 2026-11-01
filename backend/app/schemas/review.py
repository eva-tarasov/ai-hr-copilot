"""HTTP contracts for HR review."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, StrictBool


class ReviewUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reviewed: StrictBool
    note: str | None = Field(max_length=2000)
    vacancy_id: int | None = Field(default=None, gt=0)


class ReviewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    vacancy_id: int
    resume_id: int
    reviewed: bool
    note: str | None
    updated_at: datetime
