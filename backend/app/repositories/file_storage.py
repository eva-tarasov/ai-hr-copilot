"""Private local storage for bounded uploads."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import mkstemp
from typing import BinaryIO
from uuid import uuid4
import os

CHUNK_SIZE = 64 * 1024


class UploadTooLargeError(Exception):
    pass


@dataclass(frozen=True)
class StagedUpload:
    path: Path
    sha256: str
    size_bytes: int


class FileStorage:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def stage(self, stream: BinaryIO, max_bytes: int) -> StagedUpload:
        temporary_dir = self.root / "tmp"
        temporary_dir.mkdir(parents=True, exist_ok=True)
        if not temporary_dir.resolve().is_relative_to(self.root):
            raise OSError("Upload directory is outside storage root")

        descriptor, name = mkstemp(prefix="upload-", suffix=".tmp", dir=temporary_dir)
        path = Path(name)
        digest = sha256()
        total = 0
        try:
            with os.fdopen(descriptor, "wb") as output:
                while chunk := stream.read(CHUNK_SIZE):
                    total += len(chunk)
                    if total > max_bytes:
                        raise UploadTooLargeError
                    output.write(chunk)
                    digest.update(chunk)
            return StagedUpload(path=path, sha256=digest.hexdigest(), size_bytes=total)
        except Exception:
            path.unlink(missing_ok=True)
            raise

    def promote(self, staged: StagedUpload, vacancy_id: int, extension: str) -> str:
        directory = self.root / str(vacancy_id)
        directory.mkdir(parents=True, exist_ok=True)
        if not directory.resolve().is_relative_to(self.root):
            raise OSError("Vacancy directory is outside storage root")
        key = f"{vacancy_id}/{uuid4().hex}{extension}"
        destination = self.root / key
        staged.path.replace(destination)
        return key

    def discard(self, staged: StagedUpload) -> None:
        staged.path.unlink(missing_ok=True)

    def delete(self, key: str) -> None:
        path = self.root / key
        if not path.resolve().is_relative_to(self.root):
            raise OSError("File is outside storage root")
        path.unlink(missing_ok=True)
