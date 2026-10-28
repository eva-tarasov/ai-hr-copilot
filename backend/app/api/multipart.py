"""HTTP multipart parser that caps each file while request bytes arrive."""

from starlette.formparsers import MultiPartParser

MAX_FILES_PER_BATCH = 20


class BoundedMultiPartParser(MultiPartParser):
    def __init__(self, *args: object, max_file_bytes: int, **kwargs: object) -> None:
        super().__init__(*args, max_files=MAX_FILES_PER_BATCH, max_fields=0, **kwargs)
        self.max_file_bytes = max_file_bytes
        self.oversized_file_ids: set[int] = set()
        self._current_file_bytes = 0

    def on_part_begin(self) -> None:
        super().on_part_begin()
        self._current_file_bytes = 0

    def on_part_data(self, data: bytes, start: int, end: int) -> None:
        part = self._current_part
        if part.file is None:
            super().on_part_data(data, start, end)
            return

        if id(part.file) in self.oversized_file_ids:
            return
        chunk_size = end - start
        remaining = self.max_file_bytes - self._current_file_bytes
        self._current_file_bytes += chunk_size
        if chunk_size > remaining:
            if remaining > 0:
                self._file_parts_to_write.append((part, data[start : start + remaining]))
            self.oversized_file_ids.add(id(part.file))
        else:
            self._file_parts_to_write.append((part, data[start:end]))
