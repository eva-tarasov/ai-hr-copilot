"""SQLAlchemy access to uploaded resume records."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.models import AnalysisRun, Resume, ResumeAnalysis, ResumeArchive


class DuplicateResumeError(Exception):
    pass


class ArchiveDuringRunError(Exception):
    pass


class ResumeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def list_for_vacancy(self, vacancy_id: int, *, include_archived: bool = False) -> list[Resume]:
        statement = select(Resume).where(Resume.vacancy_id == vacancy_id).order_by(Resume.id)
        if not include_archived:
            statement = statement.outerjoin(ResumeArchive).where(ResumeArchive.resume_id.is_(None))
        return list(self.session.scalars(statement))

    def get(self, resume_id: int) -> Resume | None:
        return self.session.get(Resume, resume_id)

    def get_by_hash(self, vacancy_id: int, sha256: str) -> Resume | None:
        statement = select(Resume).where(Resume.vacancy_id == vacancy_id, Resume.sha256 == sha256)
        return self.session.scalar(statement)

    def is_in_analysis(self, resume_id: int) -> bool:
        return self.session.scalar(
            select(ResumeAnalysis.id).where(ResumeAnalysis.resume_id == resume_id).limit(1)
        ) is not None

    def archive(self, resume_id: int) -> Resume | None:
        # Serialize archive transitions with run creation in this local SQLite process.
        self.session.connection().exec_driver_sql("BEGIN IMMEDIATE")
        try:
            resume = self.get(resume_id)
            if resume is None:
                self.session.rollback()
                return None
            active = self.session.scalar(
                select(AnalysisRun.id).where(
                    AnalysisRun.vacancy_id == resume.vacancy_id,
                    AnalysisRun.status.in_(("pending", "running")),
                ).limit(1)
            )
            if active is not None:
                raise ArchiveDuringRunError
            if not resume.archived:
                resume.archive_record = ResumeArchive()
                self.session.commit()
            else:
                self.session.rollback()
            return resume
        except Exception:
            self.session.rollback()
            raise

    def restore(self, resume_id: int) -> Resume | None:
        resume = self.get(resume_id)
        if resume is None:
            return None
        if resume.archive_record is not None:
            self.session.delete(resume.archive_record)
            try:
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
            self.session.refresh(resume, ["archive_record"])
        return resume

    def delete(self, resume: Resume) -> None:
        self.session.delete(resume)
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

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
