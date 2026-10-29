"""One asynchronous provider interface; business services depend only on this."""

from typing import Protocol, Sequence

from backend.app.llm.contracts import CriterionSnapshot, LLMAnalysis


class LLMProvider(Protocol):
    async def analyze(
        self, text: str, criterion_snapshot: Sequence[CriterionSnapshot]
    ) -> LLMAnalysis: ...
