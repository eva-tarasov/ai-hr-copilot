"""Persisted S04 run, document, and validated criterion outcomes."""

from datetime import datetime

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base
from backend.app.models.entities import utc_now


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'completed_with_errors', 'interrupted', 'failed')",
            name="ck_analysis_runs_status",
        ),
        Index("ix_analysis_runs_vacancy_created", "vacancy_id", "created_at", "id"),
        Index(
            "uq_analysis_runs_active_vacancy",
            "vacancy_id",
            unique=True,
            sqlite_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id"), nullable=False)
    criterion_snapshot_json: Mapped[list[dict[str, object]]] = mapped_column(JSON, nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ResumeAnalysis(Base):
    __tablename__ = "resume_analyses"
    __table_args__ = (
        UniqueConstraint("run_id", "resume_id", name="uq_resume_analyses_run_resume"),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_resume_analyses_status",
        ),
        Index("ix_resume_analyses_run_status", "run_id", "status", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(String(64), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CriterionFinding(Base):
    __tablename__ = "criterion_findings"
    __table_args__ = (
        UniqueConstraint(
            "resume_analysis_id", "criterion_snapshot_id", name="uq_findings_document_criterion"
        ),
        CheckConstraint(
            "status IN ('confirmed', 'mentioned', 'not_found', 'conflicting')",
            name="ck_criterion_findings_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resume_analysis_id: Mapped[int] = mapped_column(
        ForeignKey("resume_analyses.id", ondelete="CASCADE"), nullable=False
    )
    criterion_snapshot_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    evidence_quote: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    follow_up_question: Mapped[str | None] = mapped_column(Text, nullable=True)
