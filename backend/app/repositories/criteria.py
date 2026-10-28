"""SQLAlchemy access to criteria."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models import Criterion


class CriterionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_vacancy(self, vacancy_id: int) -> list[Criterion]:
        statement = (
            select(Criterion)
            .where(Criterion.vacancy_id == vacancy_id)
            .order_by(Criterion.display_order, Criterion.id)
        )
        return list(self.session.scalars(statement))

    def get(self, criterion_id: int) -> Criterion | None:
        return self.session.get(Criterion, criterion_id)

    def next_display_order(self, vacancy_id: int) -> int:
        last = self.session.scalar(
            select(func.max(Criterion.display_order)).where(Criterion.vacancy_id == vacancy_id)
        )
        return 0 if last is None else last + 1

    def create(
        self, vacancy_id: int, description: str, priority: str, active: bool, display_order: int
    ) -> Criterion:
        criterion = Criterion(
            vacancy_id=vacancy_id,
            description=description,
            priority=priority,
            active=active,
            display_order=display_order,
        )
        self.session.add(criterion)
        self.session.commit()
        self.session.refresh(criterion)
        return criterion

    def update(self, criterion: Criterion, changes: dict[str, object]) -> Criterion:
        for field, value in changes.items():
            setattr(criterion, field, value)
        self.session.commit()
        self.session.refresh(criterion)
        return criterion

    def delete(self, criterion: Criterion) -> None:
        self.session.delete(criterion)
        self.session.commit()
