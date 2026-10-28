"""SQLAlchemy models registered for local schema creation."""

from backend.app.models.base import Base
from backend.app.models.entities import Criterion, Vacancy
from backend.app.models.resume import Resume

__all__ = ["Base", "Criterion", "Resume", "Vacancy"]
