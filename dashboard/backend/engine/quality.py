from __future__ import annotations

import json
import re

from adapters.base import LLMAdapter


_SCORE_RE = re.compile(r"SCORE:\s*([0-9]+(?:\.[0-9]+)?)", re.I)


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _parse_score_line(text: str) -> float:
    m = _SCORE_RE.search(text)
    if m:
        return _clamp01(float(m.group(1)))
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "score" in data:
            return _clamp01(float(data["score"]))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    return _clamp01(len(text) / 4000.0)


class QualityScorer:
    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    def _judge_prompt(
        self,
        label: str,
        content: str,
        criteria: list[str],
        context: str,
    ) -> str:
        crit = "\n".join(f"- {c}" for c in criteria) if criteria else "- overall quality"
        return (
            f"You are an evaluator for {label}.\n"
            f"Context:\n{context or '(none)'}\n\n"
            f"Criteria:\n{crit}\n\n"
            f"Content to rate:\n---\n{content}\n---\n\n"
            "Respond with exactly one line of the form: SCORE: <float between 0 and 1>"
        )

    async def score_section(
        self,
        content: str,
        criteria: list[str],
        context: str,
        model: str | None = None,
    ) -> float:
        prompt = self._judge_prompt("a single section", content, criteria, context)
        resp = await self._llm.generate(
            prompt,
            system="You output only the required SCORE line.",
            temperature=0.2,
            max_tokens=64,
            model=model,
        )
        return _parse_score_line(resp.content)

    async def score_document(
        self,
        sections: list[str],
        criteria: list[str],
        model: str | None = None,
    ) -> float:
        joined = "\n\n".join(f"## Section {i+1}\n{s}" for i, s in enumerate(sections))
        prompt = self._judge_prompt(
            "full document consistency",
            joined,
            criteria,
            "",
        )
        resp = await self._llm.generate(
            prompt,
            system="You output only the required SCORE line.",
            temperature=0.2,
            max_tokens=64,
            model=model,
        )
        return _parse_score_line(resp.content)

    def score_path(self, path_results: list[float]) -> float:
        if not path_results:
            return 0.0
        prod = 1.0
        for x in path_results:
            prod *= max(0.0, min(1.0, x))
        return _clamp01(prod)
