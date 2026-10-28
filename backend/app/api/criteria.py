"""Criterion HTTP endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from backend.app.api.deps import get_criterion_service
from backend.app.schemas.criteria import CriterionRead, CriterionUpdate
from backend.app.services.criteria import CriterionService

router = APIRouter(tags=["criteria"])
Criteria = Annotated[CriterionService, Depends(get_criterion_service)]


@router.patch("/criteria/{criterion_id}", response_model=CriterionRead)
def update_criterion(criterion_id: int, payload: CriterionUpdate, service: Criteria) -> CriterionRead:
    updated = service.update(criterion_id, payload.model_dump(exclude_unset=True))
    return CriterionRead.model_validate(updated)


@router.delete("/criteria/{criterion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_criterion(criterion_id: int, service: Criteria) -> None:
    service.delete(criterion_id)
