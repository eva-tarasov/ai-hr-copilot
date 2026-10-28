"""SQLAlchemy access to vacancies."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models import Vacancy


class VacancyRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list(self) -> list[Vacancy]:
        return list(self.session.scalars(select(Vacancy).order_by(Vacancy.id)))

    def get(self, vacancy_id: int) -> Vacancy | None:
        return self.session.get(Vacancy, vacancy_id)

    def create(self, title: str, description: str) -> Vacancy:
        vacancy = Vacancy(title=title, description=description)
        self.session.add(vacancy)
        self.session.commit()
        self.session.refresh(vacancy)
        return vacancy

    def update(self, vacancy: Vacancy, changes: dict[str, str]) -> Vacancy:
        for field, value in changes.items():
            setattr(vacancy, field, value)
        self.session.commit()
        self.session.refresh(vacancy)
        return vacancy
