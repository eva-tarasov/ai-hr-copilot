"""Multipart resume upload and read-only document HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException

from backend.app.api.deps import get_resume_service
from backend.app.api.multipart import BoundedMultiPartParser
from backend.app.schemas.resumes import ResumeDetail, ResumeSummary, UploadBatchResponse, UploadFileResult
from backend.app.services.resumes import ResumeService, UploadInput

router = APIRouter(tags=["resumes"])
Resumes = Annotated[ResumeService, Depends(get_resume_service)]


@router.post(
    "/vacancies/{vacancy_id}/resumes",
    response_model=UploadBatchResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "files": {"type": "array", "items": {"type": "string", "format": "binary"}}
                        },
                        "required": ["files"],
                    }
                }
            },
        }
    },
)
async def upload_resumes(vacancy_id: int, request: Request, service: Resumes) -> UploadBatchResponse:
    if not request.headers.get("content-type", "").startswith("multipart/form-data"):
        raise HTTPException(status_code=422, detail="Multipart files field is required")
    parser = BoundedMultiPartParser(
        request.headers, request.stream(), max_file_bytes=request.app.state.max_upload_bytes
    )
    try:
        form = await parser.parse()
    except (MultiPartException, KeyError):
        raise HTTPException(status_code=400, detail="Invalid multipart upload") from None

    try:
        files = form.getlist("files")
        if not files or any(not isinstance(file, UploadFile) for file in files):
            raise HTTPException(status_code=422, detail="At least one file is required")
        inputs = [
            UploadInput(
                filename=file.filename or "",
                stream=file.file,
                oversized=id(file) in parser.oversized_file_ids,
            )
            for file in files
        ]
        outcomes = await run_in_threadpool(service.upload_batch, vacancy_id, inputs)
        return UploadBatchResponse(results=[UploadFileResult.model_validate(item) for item in outcomes])
    finally:
        await form.close()


@router.get("/vacancies/{vacancy_id}/resumes", response_model=list[ResumeSummary])
def list_resumes(vacancy_id: int, service: Resumes) -> list[ResumeSummary]:
    return [ResumeSummary.model_validate(item) for item in service.list_for_vacancy(vacancy_id)]


@router.get("/resumes/{resume_id}", response_model=ResumeDetail)
def get_resume(resume_id: int, service: Resumes) -> ResumeDetail:
    return ResumeDetail.model_validate(service.get(resume_id))
