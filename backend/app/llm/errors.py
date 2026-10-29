"""Safe, machine-readable failures for later S04 handling."""


class AnalysisError(Exception):
    def __init__(self, code: str, criterion_id: int | None = None) -> None:
        self.code = code
        self.criterion_id = criterion_id
        suffix = f" (criterion_id={criterion_id})" if criterion_id is not None else ""
        super().__init__(f"{code}{suffix}")


class AnalysisInputError(AnalysisError):
    pass


class AnalysisValidationError(AnalysisError):
    pass


class ProviderError(AnalysisError):
    pass
