"""SQLAlchemy access to uploaded resume records."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import Resume


class DuplicateResumeError(Exception):
    pass


class ResumeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_vacancy(self, vacancy_id: int) -> list[Resume]:
        statement = select(Resume).where(Resume.vacancy_id == vacancy_id).order_by(Resume.id)
        return list(self.session.scalars(statement))

    def get(self, resume_id: int) -> Resume | None:
        return self.session.get(Resume, resume_id)

    def get_by_hash(self, vacancy_id: int, sha256: str) -> Resume | None:
        statement = select(Resume).where(Resume.vacancy_id == vacancy_id, Resume.sha256 == sha256)
        return self.session.scalar(statement)

    def create(self, **fields: object) -> Resume:
        resume = Resume(**fields)
        self.session.add(resume)
        try:
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise DuplicateResumeError from error
        except Exception:
            self.session.rollback()
            raise
        return resume

    def replace_extraction(
        self,
        resume: Resume,
        *,
        filename: str,
        text: str,
        file_type: str,
        storage_key: str,
        page_count: int,
        source_pages: list[dict[str, object]],
    ) -> Resume:
        resume.filename = filename
        resume.status = "ready"
        resume.extracted_text = text
        resume.parse_error = None
        resume.file_type = file_type
        resume.storage_key = storage_key
        resume.page_count = page_count
        resume.source_pages = source_pages
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return resume
