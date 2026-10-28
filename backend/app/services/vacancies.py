"""Vacancy use cases."""

from backend.app.models import Vacancy
from backend.app.repositories.vacancies import VacancyRepository
from backend.app.services.errors import NotFoundError


class VacancyService:
    def __init__(self, repository: VacancyRepository) -> None:
        self.repository = repository

    def list(self) -> list[Vacancy]:
        return self.repository.list()

    def get(self, vacancy_id: int) -> Vacancy:
        vacancy = self.repository.get(vacancy_id)
        if vacancy is None:
            raise NotFoundError(f"Vacancy {vacancy_id} not found")
        return vacancy

    def create(self, title: str, description: str) -> Vacancy:
        return self.repository.create(title, description)

    def update(self, vacancy_id: int, changes: dict[str, str]) -> Vacancy:
        return self.repository.update(self.get(vacancy_id), changes)
