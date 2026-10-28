"""Bounded per-file upload, deduplication, and extraction orchestration."""

from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Literal
from unicodedata import category

from backend.app.models import Resume
from backend.app.parsing.documents import parse_document
from backend.app.repositories.file_storage import FileStorage, StagedUpload, UploadTooLargeError
from backend.app.repositories.resumes import DuplicateResumeError, ResumeRepository
from backend.app.services.errors import NotFoundError
from backend.app.services.vacancies import VacancyService

UploadStatus = Literal["ready", "unsupported", "parse_error", "rejected"]
SUPPORTED_EXTENSIONS = {".pdf", ".docx"}


@dataclass(frozen=True)
class UploadInput:
    filename: str
    stream: BinaryIO
    oversized: bool = False


@dataclass(frozen=True)
class UploadResult:
    filename: str
    status: UploadStatus
    resume_id: int | None = None
    duplicate: bool = False
    error: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None


def safe_filename(raw: str) -> str:
    basename = raw.replace("\\", "/").rsplit("/", 1)[-1]
    cleaned = "".join(character for character in basename if category(character)[0] != "C")
    return cleaned.strip(" .")[-255:] or "unnamed"


class ResumeService:
    def __init__(
        self,
        repository: ResumeRepository,
        vacancies: VacancyService,
        storage: FileStorage,
        max_upload_bytes: int,
    ) -> None:
        self.repository = repository
        self.vacancies = vacancies
        self.storage = storage
        self.max_upload_bytes = max_upload_bytes

    def list_for_vacancy(self, vacancy_id: int) -> list[Resume]:
        self.vacancies.get(vacancy_id)
        return self.repository.list_for_vacancy(vacancy_id)

    def get(self, resume_id: int) -> Resume:
        resume = self.repository.get(resume_id)
        if resume is None:
            raise NotFoundError(f"Resume {resume_id} not found")
        return resume

    def upload_batch(self, vacancy_id: int, files: list[UploadInput]) -> list[UploadResult]:
        self.vacancies.get(vacancy_id)
        return [self._upload_one(vacancy_id, file) for file in files]

    def _upload_one(self, vacancy_id: int, file: UploadInput) -> UploadResult:
        filename = safe_filename(file.filename)
        if file.oversized:
            return UploadResult(
                filename=filename,
                status="rejected",
                error=f"File exceeds {self.max_upload_bytes} byte limit",
            )
        extension = Path(filename).suffix.lower()
        try:
            staged = self.storage.stage(file.stream, self.max_upload_bytes)
        except UploadTooLargeError:
            return UploadResult(
                filename=filename,
                status="rejected",
                error=f"File exceeds {self.max_upload_bytes} byte limit",
            )
        except Exception:
            return UploadResult(filename=filename, status="rejected", error="Could not receive file")

        storage_key: str | None = None
        try:
            existing = self.repository.get_by_hash(vacancy_id, staged.sha256)
            if existing is not None:
                return self._duplicate_result(filename, existing)

            parsed = parse_document(staged.path, extension)
            if extension in SUPPORTED_EXTENSIONS:
                storage_key = self.storage.promote(staged, vacancy_id, extension)

            resume = self.repository.create(
                vacancy_id=vacancy_id,
                filename=filename,
                sha256=staged.sha256,
                status=parsed.status,
                extracted_text=parsed.text,
                parse_error=parsed.error,
                size_bytes=staged.size_bytes,
                file_type=extension.lstrip(".") if extension in SUPPORTED_EXTENSIONS else None,
                storage_key=storage_key,
                page_count=parsed.page_count,
                source_pages=parsed.source_pages,
            )
            return UploadResult(
                filename=filename,
                status=parsed.status,
                resume_id=resume.id,
                error=parsed.error,
                sha256=staged.sha256,
                size_bytes=staged.size_bytes,
            )
        except DuplicateResumeError:
            self._clean_up(staged, storage_key)
            try:
                existing = self.repository.get_by_hash(vacancy_id, staged.sha256)
                if existing is not None:
                    return self._duplicate_result(filename, existing)
            except Exception:
                pass
            return UploadResult(filename=filename, status="rejected", error="Could not save file")
        except Exception:
            self._clean_up(staged, storage_key)
            return UploadResult(filename=filename, status="rejected", error="Could not save file")
        finally:
            self.storage.discard(staged)

    def _clean_up(self, staged: StagedUpload, storage_key: str | None) -> None:
        if storage_key is not None:
            try:
                self.storage.delete(storage_key)
            except OSError:
                pass
        self.storage.discard(staged)

    @staticmethod
    def _duplicate_result(filename: str, resume: Resume) -> UploadResult:
        return UploadResult(
            filename=filename,
            status=resume.status,
            resume_id=resume.id,
            duplicate=True,
            error=resume.parse_error,
            sha256=resume.sha256,
            size_bytes=resume.size_bytes,
        )
