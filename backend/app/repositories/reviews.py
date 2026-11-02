"""Persistence for vacancy-scoped human reviews."""
from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session
from backend.app.models import HRReview, Resume, Vacancy
from backend.app.models.entities import utc_now


class ReviewRepository:
    def __init__(self, session: Session):
        self.session = session

    def vacancy(self, vacancy_id: int):
        return self.session.get(Vacancy, vacancy_id)

    def resume(self, resume_id: int):
        return self.session.get(Resume, resume_id)

    def list(self, vacancy_id: int):
        return list(self.session.scalars(select(HRReview).where(HRReview.vacancy_id == vacancy_id).order_by(HRReview.resume_id)))

    def save(self, vacancy_id: int, resume_id: int, reviewed: bool, note: str | None):
        values = dict(vacancy_id=vacancy_id, resume_id=resume_id, reviewed=reviewed, note=note, updated_at=utc_now())
        statement = insert(HRReview).values(**values).on_conflict_do_update(
            index_elements=["vacancy_id", "resume_id"],
            set_={key: values[key] for key in ("reviewed", "note", "updated_at")},
        ).returning(HRReview)
        try:
            result = self.session.scalars(statement).one()
            self.session.commit()
            return result
        except Exception:
            self.session.rollback()
            raise
