"""Bounded in-process analysis; every database operation owns a fresh session."""

import asyncio
from collections.abc import Callable

from sqlalchemy.orm import Session, sessionmaker

from backend.app.llm.contracts import CriterionSnapshot
from backend.app.llm.errors import AnalysisInputError, AnalysisValidationError, ProviderError
from backend.app.llm.provider import LLMProvider
from backend.app.repositories.analyses import AnalysisRepository
from backend.app.services.analysis import AnalysisService

TRANSIENT_ERRORS = frozenset({"timeout", "transient_api_error"})
MAX_ATTEMPTS = 3


class BatchDispatcher:
    def __init__(self, session_factory: sessionmaker[Session], provider: LLMProvider,
                 max_concurrent: int) -> None:
        self.session_factory = session_factory
        self.analysis = AnalysisService(provider)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.tasks: set[asyncio.Task[None]] = set()

    def _db(self, operation: Callable[[AnalysisRepository], object]) -> object:
        with self.session_factory() as session:
            return operation(AnalysisRepository(session))

    def recover(self) -> None:
        self._db(lambda repo: repo.interrupt_unfinished())

    async def _async_db(self, operation: Callable[[AnalysisRepository], object]) -> object:
        # A session is created, used and closed entirely in the worker thread.
        # Wait for an in-flight operation before shutdown can dispose its engine.
        task = asyncio.create_task(asyncio.to_thread(self._db, operation))
        try:
            return await asyncio.shield(task)
        except asyncio.CancelledError:
            await task
            raise

    def schedule(self, run_id: int) -> None:
        task = asyncio.create_task(self._run(run_id))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _run(self, run_id: int) -> None:
        try:
            started = await self._async_db(lambda repo: repo.start_run(run_id))
            if not started:
                return
            run = await self._async_db(lambda repo: repo.get(run_id))
            assert run is not None
            snapshot = [CriterionSnapshot.model_validate(item) for item in run.criterion_snapshot_json]
            document_ids = await self._async_db(lambda repo: [doc.id for doc, _ in repo.documents(run_id)])
            await asyncio.gather(
                *(self._document(doc_id, snapshot) for doc_id in document_ids),
                return_exceptions=True,
            )
            await self._async_db(lambda repo: repo.finish_run(run_id))
            current = await self._async_db(lambda repo: repo.get(run_id))
            if current is not None and current.status == "running":
                await self._async_db(lambda repo: repo.interrupt_run(run_id))
        except asyncio.CancelledError:
            raise
        except Exception:
            # Database or unexpected worker failures must never leave an active run indefinitely.
            await self._async_db(lambda repo: repo.interrupt_run(run_id))

    async def _document(self, document_id: int, snapshot: list[CriterionSnapshot]) -> None:
        async with self.semaphore:
            try:
                if not await self._async_db(lambda repo: repo.start_document(document_id)):
                    return
                source = await self._async_db(lambda repo: repo.input_snapshot(document_id))
                if source is None:
                    await self._async_db(lambda repo: repo.fail_document(document_id, "input_snapshot_missing"))
                    return
                status, extracted_text, source_pages = source
                if status != "ready" or not extracted_text:
                    await self._async_db(lambda repo: repo.fail_document(document_id, "resume_not_ready"))
                    return
                for attempt in range(MAX_ATTEMPTS):
                    try:
                        result = await self.analysis.analyze(
                            extracted_text, source_pages, snapshot
                        )
                        await self._async_db(lambda repo: repo.complete_document(document_id, result))
                        return
                    except ProviderError as error:
                        if error.code in TRANSIENT_ERRORS and attempt < MAX_ATTEMPTS - 1:
                            await asyncio.sleep(0.05 * (2 ** attempt))
                            continue
                        await self._async_db(lambda repo: repo.fail_document(document_id, error.code))
                        return
                    except (AnalysisInputError, AnalysisValidationError) as error:
                        await self._async_db(lambda repo: repo.fail_document(document_id, error.code))
                        return
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._async_db(lambda repo: repo.fail_document(document_id, "internal_error"))

    async def shutdown(self) -> None:
        for task in tuple(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
        await self._async_db(lambda repo: repo.interrupt_unfinished())
