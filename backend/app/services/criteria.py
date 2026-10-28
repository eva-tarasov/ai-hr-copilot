"""Criterion use cases and vacancy ownership checks."""

from backend.app.models import Criterion
from backend.app.repositories.criteria import CriterionRepository
from backend.app.services.errors import NotFoundError
from backend.app.services.vacancies import VacancyService


class CriterionService:
    def __init__(self, repository: CriterionRepository, vacancies: VacancyService) -> None:
        self.repository = repository
        self.vacancies = vacancies

    def list_for_vacancy(self, vacancy_id: int) -> list[Criterion]:
        self.vacancies.get(vacancy_id)
        return self.repository.list_for_vacancy(vacancy_id)

    def create(
        self,
        vacancy_id: int,
        description: str,
        priority: str,
        active: bool,
        display_order: int | None,
    ) -> Criterion:
        self.vacancies.get(vacancy_id)
        order = (
            self.repository.next_display_order(vacancy_id)
            if display_order is None
            else display_order
        )
        return self.repository.create(vacancy_id, description, priority, active, order)

    def get(self, criterion_id: int) -> Criterion:
        criterion = self.repository.get(criterion_id)
        if criterion is None:
            raise NotFoundError(f"Criterion {criterion_id} not found")
        return criterion

    def update(self, criterion_id: int, changes: dict[str, object]) -> Criterion:
        return self.repository.update(self.get(criterion_id), changes)

    def delete(self, criterion_id: int) -> None:
        self.repository.delete(self.get(criterion_id))
