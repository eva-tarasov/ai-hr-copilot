"""Pydantic criterion contracts."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Priority = Literal["required", "preferred"]
CriterionDescription = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
]


class CriterionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: CriterionDescription
    priority: Priority
    active: bool = True
    display_order: int | None = Field(default=None, ge=0)


class CriterionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: CriterionDescription | None = None
    priority: Priority | None = None
    active: bool | None = None
    display_order: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def require_changes(self) -> "CriterionUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        if any(getattr(self, field) is None for field in self.model_fields_set):
            raise ValueError("Fields cannot be null")
        return self


class CriterionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vacancy_id: int
    description: str
    priority: Priority
    active: bool
    display_order: int
    updated_at: datetime
