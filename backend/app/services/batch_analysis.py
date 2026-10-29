"""S04 run submission and read models; no provider call on the request path."""

from sqlalchemy.orm import Session

from backend.app.llm.contracts import CriterionSnapshot
from backend.app.llm.errors import AnalysisInputError
from backend.app.llm.provider import LLMProvider
from backend.app.repositories.analyses import ActiveRunError, AnalysisRepository
from backend.app.repositories.criteria import CriterionRepository
from backend.app.repositories.resumes import ResumeRepository
from backend.app.repositories.vacancies import VacancyRepository
from backend.app.services.analysis import AnalysisService
from backend.app.services.errors import ConflictError, InvalidRunError, NotFoundError

SCHEMA_VERSION = "s03-v1"
PROMPT_VERSION = "s03-v1"


class BatchAnalysisService:
    def __init__(self, session: Session, provider: LLMProvider) -> None:
        self.analyses = AnalysisRepository(session)
        self.vacancies = VacancyRepository(session)
        self.criteria = CriterionRepository(session)
        self.resumes = ResumeRepository(session)
        self.provider = provider

    def create(self, vacancy_id: int) -> int:
        if self.vacancies.get(vacancy_id) is None:
            raise NotFoundError("Vacancy not found")
        criteria = [item for item in self.criteria.list_for_vacancy(vacancy_id) if item.active]
        if not criteria:
            raise InvalidRunError("no_active_criteria")
        resumes = self.resumes.list_for_vacancy(vacancy_id)
        if not resumes or not any(item.status == "ready" for item in resumes):
            raise InvalidRunError("no_ready_resumes")
        try:
            snapshot = AnalysisService.validate_snapshot(
                [CriterionSnapshot.model_validate(item) for item in criteria]
            )
        except AnalysisInputError as error:
            raise InvalidRunError(error.code) from None
        provider_name = type(self.provider).__name__.removesuffix("Provider").lower()
        model_name = getattr(self.provider, "model", None)
        try:
            run = self.analyses.create(
                vacancy_id=vacancy_id,
                snapshot=[item.model_dump(mode="json") for item in snapshot],
                resume_ids=[item.id for item in resumes],
                provider=provider_name,
                model=model_name,
                schema_version=SCHEMA_VERSION,
                prompt_version=PROMPT_VERSION,
            )
        except ActiveRunError:
            raise ConflictError("active_run_exists") from None
        return run.id

    def get(self, run_id: int) -> dict[str, object]:
        run = self.analyses.get(run_id)
        if run is None:
            raise NotFoundError("Analysis run not found")
        docs = self.analyses.documents(run_id)
        counts = {state: sum(doc.status == state for doc, _ in docs)
                  for state in ("pending", "running", "completed", "failed", "interrupted")}
        return {
            "id": run.id, "vacancy_id": run.vacancy_id, "status": run.status,
            "provider": run.provider, "model": run.model,
            "schema_version": run.schema_version, "prompt_version": run.prompt_version,
            "criterion_snapshot": run.criterion_snapshot_json,
            "created_at": run.created_at, "started_at": run.started_at,
            "completed_at": run.completed_at, "total": len(docs), **counts,
        }

    def results(self, run_id: int) -> dict[str, object]:
        run = self.analyses.get(run_id)
        if run is None:
            raise NotFoundError("Analysis run not found")
        return {
            "run_id": run_id,
            "results": [
                {
                    "resume_id": resume.id, "filename": resume.filename,
                    "status": doc.status, "error": doc.error,
                    "started_at": doc.started_at, "completed_at": doc.completed_at,
                    "findings": [
                        {"criterion_id": item.criterion_snapshot_id, "status": item.status,
                         "evidence_quote": item.evidence_quote, "evidence_page": item.evidence_page,
                         "follow_up_question": item.follow_up_question}
                        for item in self.analyses.findings(doc.id)
                    ],
                } for doc, resume in self.analyses.documents(run_id)
            ],
        }
