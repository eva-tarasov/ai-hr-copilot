"""HTTP endpoints for local batch submission and polling."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from backend.app.api.deps import get_batch_analysis_service
from backend.app.schemas.analyses import ResultsRead, RunRead, RunSummary
from backend.app.services.batch_analysis import BatchAnalysisService

router = APIRouter(tags=["analyses"])
Batch = Annotated[BatchAnalysisService, Depends(get_batch_analysis_service)]


@router.get("/vacancies/{vacancy_id}/analyses", response_model=list[RunSummary])
def list_analyses(vacancy_id: int, service: Batch) -> list[RunSummary]:
    return [RunSummary.model_validate(item) for item in service.list_for_vacancy(vacancy_id)]


@router.post("/vacancies/{vacancy_id}/analyses", response_model=RunRead,
             status_code=status.HTTP_202_ACCEPTED)
async def start_analysis(vacancy_id: int, service: Batch, request: Request) -> RunRead:
    run_id = service.create(vacancy_id)
    response = RunRead.model_validate(service.get(run_id))
    request.app.state.batch_dispatcher.schedule(run_id)
    return response


@router.get("/analyses/{run_id}", response_model=RunRead)
def get_analysis(run_id: int, service: Batch) -> RunRead:
    return RunRead.model_validate(service.get(run_id))


@router.get("/analyses/{run_id}/results", response_model=ResultsRead)
def get_results(run_id: int, service: Batch) -> ResultsRead:
    return ResultsRead.model_validate(service.results(run_id))
