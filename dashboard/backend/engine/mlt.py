from __future__ import annotations

import random

from pydantic import BaseModel, Field

from adapters.base import LLMAdapter

from .quality import QualityScorer


class MLTResult(BaseModel):
    final_document: list[str]
    score_history: list[float]
    accepted: int = 0
    rejected: int = 0
    total_iterations: int = 0


class MLTEngine:
    def __init__(self, llm: LLMAdapter, scorer: QualityScorer | None = None) -> None:
        self._llm = llm
        self._scorer = scorer or QualityScorer(llm)

    async def initialize(self, task: str, model: str | None = None) -> list[str]:
        prompt = (
            f"Art Bible drafting task:\n{task}\n\n"
            "Produce exactly 5 sections separated by lines containing only ---SECTION---"
        )
        resp = await self._llm.generate(
            prompt,
            system="Write structured creative specification sections.",
            temperature=0.85,
            max_tokens=4096,
            model=model,
        )
        parts = [p.strip() for p in resp.content.split("---SECTION---") if p.strip()]
        if len(parts) < 5:
            parts = (parts + [resp.content])[:5]
        while len(parts) < 5:
            parts.append(parts[-1])
        return parts[:5]

    async def mutate(
        self,
        document: list[str],
        section_index: int,
        model: str | None = None,
    ) -> list[str]:
        i = max(0, min(len(document) - 1, section_index))
        prompt = (
            "Rewrite only the target section; keep others conceptually stable.\n"
            f"Full document (for context):\n{document}\n\n"
            f"Target section index: {i}\nCurrent section text:\n{document[i]}\n\n"
            "Return only the revised section body."
        )
        resp = await self._llm.generate(
            prompt,
            system="Return only the mutated section text.",
            temperature=0.9,
            max_tokens=2048,
            model=model,
        )
        new_doc = list(document)
        new_doc[i] = resp.content.strip()
        return new_doc

    def accept_reject(
        self,
        current: list[str],
        proposed: list[str],
        current_score: float,
        proposed_score: float,
    ) -> bool:
        _ = current
        f_cur = max(1e-9, current_score)
        f_prop = max(1e-9, proposed_score)
        alpha = min(1.0, f_prop / f_cur)
        return random.random() < alpha

    async def run(
        self,
        task: str,
        model: str | None,
        iterations: int,
        criteria: list[str] | None = None,
    ) -> MLTResult:
        crit = criteria or ["coherence", "creative clarity"]
        current = await self.initialize(task, model=model)
        history: list[float] = []
        accepted = 0
        rejected = 0
        cur_score = await self._scorer.score_document(current, crit, model=model)
        history.append(cur_score)
        for _ in range(iterations):
            idx = random.randrange(len(current))
            proposed = await self.mutate(current, idx, model=model)
            prop_score = await self._scorer.score_document(proposed, crit, model=model)
            if self.accept_reject(current, proposed, cur_score, prop_score):
                current = proposed
                cur_score = prop_score
                accepted += 1
            else:
                rejected += 1
            history.append(cur_score)
        return MLTResult(
            final_document=current,
            score_history=history,
            accepted=accepted,
            rejected=rejected,
            total_iterations=iterations,
        )
