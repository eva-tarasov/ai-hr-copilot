"""Vacancy and criterion records for S01."""

from datetime import UTC, datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.models.base import Base


def utc_now() -> datetime:
    return datetime.now(UTC)


class Vacancy(Base):
    __tablename__ = "vacancies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )


class Criterion(Base):
    __tablename__ = "criteria"
    __table_args__ = (
        CheckConstraint("priority IN ('required', 'preferred')", name="ck_criteria_priority"),
        CheckConstraint("display_order >= 0", name="ck_criteria_display_order"),
        Index("ix_criteria_vacancy_order", "vacancy_id", "display_order", "id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(
        ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False
    )
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    priority: Mapped[str] = mapped_column(String(9), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False
    )
