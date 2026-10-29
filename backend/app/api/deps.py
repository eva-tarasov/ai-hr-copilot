"""Request-scoped sessions and service wiring for HTTP routes."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.app.repositories.criteria import CriterionRepository
from backend.app.repositories.resumes import ResumeRepository
from backend.app.repositories.vacancies import VacancyRepository
from backend.app.services.criteria import CriterionService
from backend.app.services.resumes import ResumeService
from backend.app.services.vacancies import VacancyService
from backend.app.services.batch_analysis import BatchAnalysisService
from backend.app.repositories.file_storage import FileStorage


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]


def get_vacancy_service(session: DbSession) -> VacancyService:
    return VacancyService(VacancyRepository(session))


def get_criterion_service(session: DbSession) -> CriterionService:
    vacancies = VacancyService(VacancyRepository(session))
    return CriterionService(CriterionRepository(session), vacancies)


def get_resume_service(request: Request, session: DbSession) -> ResumeService:
    vacancies = VacancyService(VacancyRepository(session))
    storage: FileStorage = request.app.state.file_storage
    return ResumeService(
        ResumeRepository(session), vacancies, storage, request.app.state.max_upload_bytes
    )


def get_batch_analysis_service(request: Request, session: DbSession) -> BatchAnalysisService:
    return BatchAnalysisService(session, request.app.state.analysis_provider)
