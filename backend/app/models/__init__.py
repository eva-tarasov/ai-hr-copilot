"""SQLAlchemy models registered for local schema creation."""

from backend.app.models.base import Base
from backend.app.models.entities import Criterion, Vacancy

__all__ = ["Base", "Criterion", "Vacancy"]
