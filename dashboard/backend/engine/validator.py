from __future__ import annotations

import random

from pydantic import BaseModel, Field

from adapters.base import LLMAdapter

from .quality import _parse_score_line


class ValidationResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    should_continue: bool
    weight: float = Field(ge=0.0)
    reasoning: str = ""


class Validator:
    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    async def score(
        self,
        content: str,
        context: str,
        criteria: list[str],
        model: str | None = None,
    ) -> float:
        crit = "\n".join(f"- {c}" for c in criteria) if criteria else "- usefulness"
        prompt = (
            "You are an LLM-as-judge evaluator.\n"
            f"Context:\n{context or '(none)'}\n\n"
            f"Criteria:\n{crit}\n\n"
            f"Candidate:\n---\n{content}\n---\n\n"
            "Respond with exactly one line: SCORE: <float between 0 and 1>"
        )
        resp = await self._llm.generate(
            prompt,
            system="You output only the required SCORE line.",
            temperature=0.2,
            max_tokens=96,
            model=model,
        )
        return _parse_score_line(resp.content)

    def russian_roulette(self, score: float, threshold: float) -> tuple[bool, float]:
        if threshold <= 0:
            return True, 1.0
        q = min(score / threshold, 1.0)
        if q <= 0:
            return False, 0.0
        if random.random() < q:
            return True, 1.0 / q
        return False, 0.0
