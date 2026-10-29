"""Conservative, deterministic offline provider for synthetic demonstrations."""

import re
from collections.abc import Sequence

from backend.app.llm.contracts import CriterionFinding, CriterionSnapshot, LLMAnalysis

_INSTRUCTION_LINE = re.compile(
    r"^\s*(?:ignore|disregard|override|system:|developer:|assistant:|output|respond|return|instructions?:)",
    re.IGNORECASE,
)
_NEGATIVE = re.compile(
    r"\b(?:no experience|never used|not used|have not used|do not have)\b",
    re.IGNORECASE,
)
_DIRECT = re.compile(
    r"\b(?:experience|used|built|worked with|implemented|developed|led)\b",
    re.IGNORECASE,
)


class FakeProvider:
    async def analyze(
        self, text: str, criterion_snapshot: Sequence[CriterionSnapshot]
    ) -> LLMAnalysis:
        lines: list[tuple[int, int, str]] = []
        position = 0
        for raw_line in text.splitlines(keepends=True):
            line = raw_line.rstrip("\r\n")
            lines.append((position, position + len(line), line))
            position += len(raw_line)

        findings: list[CriterionFinding] = []
        for criterion in criterion_snapshot:
            phrase = re.compile(
                rf"(?<!\w){re.escape(criterion.description.strip())}(?!\w)",
                re.IGNORECASE,
            )
            positive: list[tuple[int, int, str]] = []
            negative: list[tuple[int, int, str]] = []
            mentions: list[tuple[int, int, str]] = []
            for line in lines:
                if _INSTRUCTION_LINE.match(line[2]) or not phrase.search(line[2]):
                    continue
                if _NEGATIVE.search(line[2]):
                    negative.append(line)
                elif _DIRECT.search(line[2]):
                    positive.append(line)
                else:
                    mentions.append(line)

            if positive and negative:
                first, last = sorted((positive[0], negative[0]), key=lambda item: item[0])
                findings.append(
                    CriterionFinding(
                        criterion_id=criterion.id,
                        status="conflicting",
                        evidence_quote=text[first[0] : last[1]],
                        evidence_page=None,
                        follow_up_question="Clarify the contradictory experience statements.",
                    )
                )
            elif positive:
                findings.append(
                    CriterionFinding(
                        criterion_id=criterion.id,
                        status="confirmed",
                        evidence_quote=positive[0][2].strip(),
                        evidence_page=None,
                        follow_up_question=None,
                    )
                )
            elif mentions or negative:
                line = (mentions or negative)[0]
                findings.append(
                    CriterionFinding(
                        criterion_id=criterion.id,
                        status="mentioned",
                        evidence_quote=line[2].strip(),
                        evidence_page=None,
                        follow_up_question="Ask the candidate to clarify their experience.",
                    )
                )
            else:
                findings.append(
                    CriterionFinding(
                        criterion_id=criterion.id,
                        status="not_found",
                        evidence_quote=None,
                        evidence_page=None,
                        follow_up_question="Ask about this criterion during human review.",
                    )
                )
        return LLMAnalysis(findings=findings)
