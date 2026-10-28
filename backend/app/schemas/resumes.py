"""HTTP contracts for resume uploads and extraction results."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

ResumeStatus = Literal["ready", "unsupported", "parse_error"]
UploadStatus = Literal["ready", "unsupported", "parse_error", "rejected"]


class SourcePage(BaseModel):
    page: int
    text: str


class ResumeSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    vacancy_id: int
    filename: str
    sha256: str
    status: ResumeStatus
    parse_error: str | None
    created_at: datetime
    size_bytes: int
    file_type: str | None
    page_count: int


class ResumeDetail(ResumeSummary):
    extracted_text: str | None
    source_pages: list[SourcePage]


class UploadFileResult(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    filename: str
    status: UploadStatus
    resume_id: int | None
    duplicate: bool
    error: str | None
    sha256: str | None
    size_bytes: int | None


class UploadBatchResponse(BaseModel):
    results: list[UploadFileResult]
