"""Vacancy and nested criterion HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.app.api.deps import get_criterion_service, get_vacancy_service
from backend.app.schemas.criteria import CriterionCreate, CriterionRead
from backend.app.schemas.vacancies import VacancyCreate, VacancyRead, VacancyUpdate
from backend.app.services.criteria import CriterionService
from backend.app.services.vacancies import VacancyService

router = APIRouter(tags=["vacancies"])
Vacancies = Annotated[VacancyService, Depends(get_vacancy_service)]
Criteria = Annotated[CriterionService, Depends(get_criterion_service)]


@router.get("/vacancies", response_model=list[VacancyRead])
def list_vacancies(service: Vacancies) -> list[VacancyRead]:
    return [VacancyRead.model_validate(item) for item in service.list()]


@router.post("/vacancies", response_model=VacancyRead, status_code=status.HTTP_201_CREATED)
def create_vacancy(payload: VacancyCreate, service: Vacancies) -> VacancyRead:
    return VacancyRead.model_validate(service.create(payload.title, payload.description))


@router.get("/vacancies/{vacancy_id}", response_model=VacancyRead)
def get_vacancy(vacancy_id: int, service: Vacancies) -> VacancyRead:
    return VacancyRead.model_validate(service.get(vacancy_id))


@router.patch("/vacancies/{vacancy_id}", response_model=VacancyRead)
def update_vacancy(vacancy_id: int, payload: VacancyUpdate, service: Vacancies) -> VacancyRead:
    updated = service.update(vacancy_id, payload.model_dump(exclude_unset=True))
    return VacancyRead.model_validate(updated)


@router.get("/vacancies/{vacancy_id}/criteria", response_model=list[CriterionRead])
def list_criteria(vacancy_id: int, service: Criteria) -> list[CriterionRead]:
    return [
        CriterionRead.model_validate(item)
        for item in service.list_for_vacancy(vacancy_id)
    ]


@router.post(
    "/vacancies/{vacancy_id}/criteria",
    response_model=CriterionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_criterion(vacancy_id: int, payload: CriterionCreate, service: Criteria) -> CriterionRead:
    created = service.create(
        vacancy_id,
        payload.description,
        payload.priority,
        payload.active,
        payload.display_order,
    )
    return CriterionRead.model_validate(created)
