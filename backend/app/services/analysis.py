"""Validate provider findings against the exact snapshot and source document."""

from collections.abc import Mapping, Sequence
import re
from pydantic import ValidationError

from backend.app.llm.contracts import CriterionFinding, CriterionSnapshot, LLMAnalysis, SourcePage
from backend.app.llm.errors import AnalysisInputError, AnalysisValidationError
from backend.app.llm.provider import LLMProvider


def _normalize_whitespace(value: str) -> str:
    return " ".join(value.split())


_GENERIC_CRITERION_WORDS = {
    "and", "for", "from", "in", "of", "the", "with", "year", "years", "experience",
    "knowledge", "skill", "skills", "в", "и", "лет", "опыт", "по", "работа", "работы",
    "с", "знание", "знания",
}
_WEAK_OR_NEGATIVE = re.compile(
    r"\b(?:familiar with|interested in|learning|no experience|never used|not used|have not used)\b",
    re.IGNORECASE,
)
_INSTRUCTION_EVIDENCE = re.compile(
    r"\b(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior|above)\s+instructions\b"
    r"|\b(?:system prompt|developer message)\b"
    r"|\b(?:output|respond with|return)\s+(?:only\s+)?(?:confirmed|json)\b",
    re.IGNORECASE,
)


def _quote_is_relevant(quote: str, description: str) -> bool:
    words = [
        word for word in re.findall(r"[^\W_]+", description.casefold())
        if len(word) > 1 and word not in _GENERIC_CRITERION_WORDS
    ]
    if not words:
        return description.casefold().strip() in quote.casefold()
    quoted_words = set(re.findall(r"[^\W_]+", quote.casefold()))
    return any(word in quoted_words for word in words)


class AnalysisService:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    async def analyze(
        self,
        extracted_text: str,
        source_pages: Sequence[SourcePage | Mapping[str, object]],
        criterion_snapshot: Sequence[CriterionSnapshot],
    ) -> LLMAnalysis:
        if not extracted_text or not any(character.isalnum() for character in extracted_text):
            raise AnalysisInputError("unusable_text")
        if not criterion_snapshot:
            raise AnalysisInputError("empty_snapshot")
        try:
            snapshots = [CriterionSnapshot.model_validate(item) for item in criterion_snapshot]
            pages = [SourcePage.model_validate(item) for item in source_pages]
        except ValidationError:
            raise AnalysisInputError("invalid_source_input") from None

        ids = [item.id for item in snapshots]
        if len(ids) != len(set(ids)):
            raise AnalysisInputError("duplicate_snapshot_id")
        if len({item.vacancy_id for item in snapshots}) != 1:
            raise AnalysisInputError("mixed_vacancy_snapshot")
        if len({item.page for item in pages}) != len(pages):
            raise AnalysisInputError("duplicate_source_page")

        raw = await self.provider.analyze(extracted_text, snapshots)
        try:
            payload = (
                raw.model_dump(mode="python", warnings=False)
                if isinstance(raw, LLMAnalysis)
                else raw
            )
            analysis = LLMAnalysis.model_validate(payload)
        except (ValidationError, AttributeError, TypeError):
            raise AnalysisValidationError("invalid_structure") from None

        findings_by_id: dict[int, CriterionFinding] = {}
        for finding in analysis.findings:
            if finding.criterion_id in findings_by_id:
                raise AnalysisValidationError("duplicate_criterion_id", finding.criterion_id)
            if finding.criterion_id not in ids:
                raise AnalysisValidationError("unknown_criterion_id", finding.criterion_id)
            findings_by_id[finding.criterion_id] = finding
        if missing := set(ids) - findings_by_id.keys():
            raise AnalysisValidationError("missing_criterion_id", min(missing))

        validated = [
            self._validate_evidence(findings_by_id[item.id], item, extracted_text, pages)
            for item in snapshots
        ]
        return LLMAnalysis(findings=validated)

    @staticmethod
    def _validate_evidence(
        finding: CriterionFinding,
        criterion: CriterionSnapshot,
        text: str,
        pages: list[SourcePage],
    ) -> CriterionFinding:
        if finding.status == "not_found":
            return finding

        quote = _normalize_whitespace(finding.evidence_quote or "")
        if not quote or quote not in _normalize_whitespace(text):
            raise AnalysisValidationError("invalid_quote", finding.criterion_id)
        if _INSTRUCTION_EVIDENCE.search(quote):
            raise AnalysisValidationError("untrusted_instruction_evidence", finding.criterion_id)
        if not _quote_is_relevant(quote, criterion.description):
            raise AnalysisValidationError("evidence_mismatch", finding.criterion_id)
        if finding.status == "confirmed" and _WEAK_OR_NEGATIVE.search(quote):
            raise AnalysisValidationError("unsupported_status", finding.criterion_id)

        if not pages:
            if finding.evidence_page is not None:
                raise AnalysisValidationError("invalid_page", finding.criterion_id)
            return finding

        matching_pages = [
            page.page for page in pages if quote in _normalize_whitespace(page.text)
        ]
        if not matching_pages:
            raise AnalysisValidationError("invalid_page", finding.criterion_id)
        if finding.evidence_page is not None:
            if finding.evidence_page not in matching_pages:
                raise AnalysisValidationError("invalid_page", finding.criterion_id)
            return finding
        return finding.model_copy(update={"evidence_page": matching_pages[0]})
