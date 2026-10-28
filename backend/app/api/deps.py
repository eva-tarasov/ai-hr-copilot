"""Request-scoped sessions and service wiring for HTTP routes."""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from backend.app.repositories.criteria import CriterionRepository
from backend.app.repositories.vacancies import VacancyRepository
from backend.app.services.criteria import CriterionService
from backend.app.services.vacancies import VacancyService


def get_session(request: Request) -> Iterator[Session]:
    with request.app.state.session_factory() as session:
        yield session


DbSession = Annotated[Session, Depends(get_session)]


def get_vacancy_service(session: DbSession) -> VacancyService:
    return VacancyService(VacancyRepository(session))


def get_criterion_service(session: DbSession) -> CriterionService:
    vacancies = VacancyService(VacancyRepository(session))
    return CriterionService(CriterionRepository(session), vacancies)
