"""Stored upload and extraction outcome for one vacancy."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.models.base import Base
from backend.app.models.entities import utc_now


class Resume(Base):
    __tablename__ = "resumes"
    __table_args__ = (
        UniqueConstraint("vacancy_id", "sha256", name="uq_resumes_vacancy_sha256"),
        CheckConstraint(
            "status IN ('ready', 'unsupported', 'parse_error')", name="ck_resumes_status"
        ),
        Index("ix_resumes_vacancy_created", "vacancy_id", "created_at", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_error: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    file_type: Mapped[str | None] = mapped_column(String(8), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    source_pages: Mapped[list[dict[str, object]]] = mapped_column(JSON, default=list, nullable=False)
    archive_record: Mapped[ResumeArchive | None] = relationship(
        back_populates="resume", cascade="all, delete-orphan", passive_deletes=True,
        uselist=False, lazy="selectin",
    )

    @property
    def archived(self) -> bool:
        return self.archive_record is not None

    @property
    def archived_at(self) -> datetime | None:
        if self.archive_record is None:
            return None
        value = self.archive_record.archived_at
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class ResumeArchive(Base):
    __tablename__ = "resume_archives"

    resume_id: Mapped[int] = mapped_column(
        ForeignKey("resumes.id", ondelete="CASCADE"), primary_key=True
    )
    archived_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    resume: Mapped[Resume] = relationship(back_populates="archive_record")
