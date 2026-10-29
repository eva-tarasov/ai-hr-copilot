"""SQLAlchemy persistence for local analysis runs and per-document outcomes."""

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.llm.contracts import LLMAnalysis
from backend.app.models import AnalysisRun, CriterionFinding, Resume, ResumeAnalysis
from backend.app.models.entities import utc_now
from backend.app.models.run_states import DOCUMENT_TRANSITIONS, RUN_TRANSITIONS, require_transition


class ActiveRunError(Exception):
    pass


class AnalysisRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, vacancy_id: int, snapshot: list[dict[str, object]],
               resume_ids: list[int], provider: str, model: str | None,
               schema_version: str, prompt_version: str) -> AnalysisRun:
        run = AnalysisRun(
            vacancy_id=vacancy_id, criterion_snapshot_json=snapshot, provider=provider,
            model=model, schema_version=schema_version, prompt_version=prompt_version,
        )
        self.session.add(run)
        try:
            self.session.flush()
            self.session.add_all(
                ResumeAnalysis(run_id=run.id, resume_id=resume_id) for resume_id in resume_ids
            )
            self.session.commit()
        except IntegrityError as error:
            self.session.rollback()
            raise ActiveRunError from error
        except Exception:
            self.session.rollback()
            raise
        return run

    def get(self, run_id: int) -> AnalysisRun | None:
        return self.session.get(AnalysisRun, run_id)

    def documents(self, run_id: int) -> list[tuple[ResumeAnalysis, Resume]]:
        return list(self.session.execute(
            select(ResumeAnalysis, Resume)
            .join(Resume, Resume.id == ResumeAnalysis.resume_id)
            .where(ResumeAnalysis.run_id == run_id)
            .order_by(ResumeAnalysis.id)
        ))

    def document(self, document_id: int) -> tuple[ResumeAnalysis, Resume] | None:
        return self.session.execute(
            select(ResumeAnalysis, Resume)
            .join(Resume, Resume.id == ResumeAnalysis.resume_id)
            .where(ResumeAnalysis.id == document_id)
        ).one_or_none()

    def findings(self, document_id: int) -> list[CriterionFinding]:
        return list(self.session.scalars(
            select(CriterionFinding)
            .where(CriterionFinding.resume_analysis_id == document_id)
            .order_by(CriterionFinding.id)
        ))

    def start_run(self, run_id: int) -> bool:
        run = self.get(run_id)
        if run is None or run.status != "pending":
            return False
        require_transition(RUN_TRANSITIONS, run.status, "running")
        changed = self.session.execute(
            update(AnalysisRun).where(AnalysisRun.id == run_id, AnalysisRun.status == "pending")
            .values(status="running", started_at=utc_now())
        ).rowcount
        self.session.commit()
        return bool(changed)

    def start_document(self, document_id: int) -> bool:
        document = self.session.get(ResumeAnalysis, document_id)
        if document is None or document.status != "pending":
            return False
        require_transition(DOCUMENT_TRANSITIONS, document.status, "running")
        changed = self.session.execute(
            update(ResumeAnalysis)
            .where(ResumeAnalysis.id == document_id, ResumeAnalysis.status == "pending")
            .values(status="running", started_at=utc_now())
        ).rowcount
        self.session.commit()
        return bool(changed)

    def complete_document(self, document_id: int, analysis: LLMAnalysis) -> None:
        document = self.session.get(ResumeAnalysis, document_id)
        if document is None or document.status != "running":
            return
        require_transition(DOCUMENT_TRANSITIONS, document.status, "completed")
        self.session.add_all(
            CriterionFinding(
                resume_analysis_id=document_id, criterion_snapshot_id=item.criterion_id,
                status=item.status, evidence_quote=item.evidence_quote,
                evidence_page=item.evidence_page, follow_up_question=item.follow_up_question,
            ) for item in analysis.findings
        )
        document.status = "completed"
        document.completed_at = utc_now()
        try:
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def fail_document(self, document_id: int, code: str) -> None:
        document = self.session.get(ResumeAnalysis, document_id)
        if document is None or document.status not in ("pending", "running"):
            return
        require_transition(DOCUMENT_TRANSITIONS, document.status, "failed")
        self.session.execute(
            update(ResumeAnalysis)
            .where(ResumeAnalysis.id == document_id, ResumeAnalysis.status.in_(("pending", "running")))
            .values(status="failed", error=code, completed_at=utc_now())
        )
        self.session.commit()

    def finish_run(self, run_id: int) -> None:
        run = self.get(run_id)
        if run is None or run.status != "running":
            return
        statuses = [item.status for item, _ in self.documents(run_id)]
        if any(item in ("pending", "running") for item in statuses):
            return
        failed = sum(item in ("failed", "interrupted") for item in statuses)
        succeeded = sum(item == "completed" for item in statuses)
        target = "completed_with_errors" if failed and succeeded else "failed" if failed else "completed"
        require_transition(RUN_TRANSITIONS, run.status, target)
        run.status = target
        run.completed_at = utc_now()
        self.session.commit()

    def interrupt_unfinished(self) -> None:
        active = select(AnalysisRun.id).where(AnalysisRun.status.in_(("pending", "running")))
        self.session.execute(
            update(ResumeAnalysis)
            .where(ResumeAnalysis.run_id.in_(active), ResumeAnalysis.status.in_(("pending", "running")))
            .values(status="interrupted", error="interrupted", completed_at=utc_now())
        )
        self.session.execute(
            update(AnalysisRun)
            .where(AnalysisRun.status.in_(("pending", "running")))
            .values(status="interrupted", completed_at=utc_now())
        )
        self.session.commit()

    def interrupt_run(self, run_id: int) -> None:
        self.session.execute(
            update(ResumeAnalysis)
            .where(ResumeAnalysis.run_id == run_id, ResumeAnalysis.status.in_(("pending", "running")))
            .values(status="interrupted", error="interrupted", completed_at=utc_now())
        )
        self.session.execute(
            update(AnalysisRun)
            .where(AnalysisRun.id == run_id, AnalysisRun.status.in_(("pending", "running")))
            .values(status="interrupted", completed_at=utc_now())
        )
        self.session.commit()
