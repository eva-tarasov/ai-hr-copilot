"""HTTP endpoints for persistent human review."""
from typing import Annotated
from fastapi import APIRouter, Depends
from backend.app.api.deps import DbSession
from backend.app.repositories.reviews import ReviewRepository
from backend.app.schemas.review import ReviewRead, ReviewUpdate
from backend.app.services.reviews import ReviewService

router = APIRouter(tags=["reviews"])


def service(session: DbSession) -> ReviewService:
    return ReviewService(ReviewRepository(session))


Reviews = Annotated[ReviewService, Depends(service)]


@router.get("/vacancies/{vacancy_id}/reviews", response_model=list[ReviewRead])
def list_reviews(vacancy_id: int, reviews: Reviews):
    return reviews.list(vacancy_id)


@router.patch("/resumes/{resume_id}/review", response_model=ReviewRead)
def update_review(resume_id: int, payload: ReviewUpdate, reviews: Reviews):
    return reviews.save(resume_id, payload.reviewed, payload.note, payload.vacancy_id)
