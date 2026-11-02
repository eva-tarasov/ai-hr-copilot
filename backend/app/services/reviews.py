"""Validate scope before reading or saving HR review."""
from backend.app.repositories.reviews import ReviewRepository
from backend.app.services.errors import NotFoundError


class ReviewService:
    def __init__(self, repository: ReviewRepository):
        self.repository = repository

    def list(self, vacancy_id: int):
        if self.repository.vacancy(vacancy_id) is None:
            raise NotFoundError("Vacancy not found")
        return self.repository.list(vacancy_id)

    def save(self, resume_id: int, reviewed: bool, note: str | None, vacancy_id: int | None):
        resume = self.repository.resume(resume_id)
        if resume is None or (vacancy_id is not None and vacancy_id != resume.vacancy_id):
            raise NotFoundError("Resume not found in vacancy")
        if self.repository.vacancy(resume.vacancy_id) is None:
            raise NotFoundError("Vacancy not found")
        return self.repository.save(resume.vacancy_id, resume_id, reviewed, note)
