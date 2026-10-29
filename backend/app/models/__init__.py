"""SQLAlchemy models registered for local schema creation."""

from backend.app.models.base import Base
from backend.app.models.analysis import AnalysisRun, CriterionFinding, ResumeAnalysis
from backend.app.models.entities import Criterion, Vacancy
from backend.app.models.resume import Resume

__all__ = [
    "AnalysisRun", "Base", "Criterion", "CriterionFinding", "Resume",
    "ResumeAnalysis", "Vacancy",
]
