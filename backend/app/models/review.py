"""Human review of a resume within its vacancy."""

from datetime import datetime
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from backend.app.models.base import Base
from backend.app.models.entities import utc_now


class HRReview(Base):
    __tablename__ = "hr_reviews"
    __table_args__ = (UniqueConstraint("vacancy_id", "resume_id", name="uq_hr_review_vacancy_resume"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vacancy_id: Mapped[int] = mapped_column(ForeignKey("vacancies.id", ondelete="CASCADE"), nullable=False)
    resume_id: Mapped[int] = mapped_column(ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    reviewed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
