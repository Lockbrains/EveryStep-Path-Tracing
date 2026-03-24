"""Metropolis Light Transport with real multi-dimensional scoring.

MLT iteratively refines a complete document by mutating individual
sections and accepting/rejecting via Metropolis-Hastings. Now uses
the real Scorer + Benchmark-derived criteria instead of hardcoded ones.
Mutations are guided by feedback — sections that score lowest are
prioritized for mutation.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from typing import Union

from adapters.base import LLMAdapter
from .benchmark import Benchmark
from .scorer import EnsembleScorer, MultiDimScore, Scorer

ScorerLike = Union[Scorer, EnsembleScorer]


class MLTResult(BaseModel):
    final_document: list[str]
    score_history: list[float] = Field(default_factory=list)
    accepted: int = 0
    rejected: int = 0
    total_iterations: int = 0
    final_score: MultiDimScore | None = None


class MLTEngine:
    def __init__(self, llm: LLMAdapter, scorer: ScorerLike | None = None) -> None:
        self._llm = llm
        self._scorer: ScorerLike = scorer or Scorer(llm)

    async def mutate(
        self,
        document: list[str],
        section_index: int,
        weakness_hint: str = "",
        model: str | None = None,
    ) -> list[str]:
        i = max(0, min(len(document) - 1, section_index))
        context_parts = []
        for j, s in enumerate(document):
            if j == i:
                context_parts.append(f"[SECTION {j + 1} — TARGET]\n{s}")
            else:
                context_parts.append(f"[Section {j + 1}]\n{s[:500]}")
        context = "\n\n".join(context_parts)

        hint = ""
        if weakness_hint:
            hint = f"\n\nThe evaluator noted this weakness to address:\n{weakness_hint}\n"

        prompt = (
            f"Revise ONLY section {i + 1}. Keep all other sections conceptually stable.\n\n"
            f"Full document:\n{context}\n"
            f"{hint}\n"
            f"Return only the revised text for section {i + 1}."
        )
        resp = await self._llm.generate(
            prompt,
            system="Return only the mutated section text. No preamble.",
            temperature=0.85,
            max_tokens=2048,
            model=model,
        )
        new_doc = list(document)
        new_doc[i] = resp.content.strip()
        return new_doc

    @staticmethod
    def accept_reject(current_score: float, proposed_score: float) -> bool:
        f_cur = max(1e-9, current_score)
        f_prop = max(1e-9, proposed_score)
        alpha = min(1.0, f_prop / f_cur)
        return random.random() < alpha

    def _pick_mutation_target(
        self, document: list[str], score: MultiDimScore
    ) -> tuple[int, str]:
        """Pick the section to mutate, biased toward weakest dimensions.

        For simplicity, we use a weighted random choice where sections
        corresponding to weaker dimensions have higher probability.
        If we can't map dimensions to sections, pick uniformly.
        """
        n = len(document)
        if not score.dimension_scores or n == 0:
            return random.randrange(n), ""

        weakest = score.weakest_dimensions(2)
        hint = weakest[0].suggestion if weakest else ""

        weights = [1.0] * n
        for ds in score.dimension_scores:
            if ds.score < 0.6:
                idx = hash(ds.dimension) % n
                weights[idx] += (1.0 - ds.score) * 2.0

        total = sum(weights)
        r = random.random() * total
        cumulative = 0.0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return i, hint
        return n - 1, hint

    async def run(
        self,
        document: list[str],
        benchmark: Benchmark,
        model: str | None = None,
        iterations: int = 10,
    ) -> MLTResult:
        current = list(document)
        cur_score = await self._scorer.score_document(current, benchmark, model=model)
        history = [cur_score.aggregate]
        accepted = 0
        rejected = 0

        for _ in range(iterations):
            idx, hint = self._pick_mutation_target(current, cur_score)
            proposed = await self.mutate(current, idx, weakness_hint=hint, model=model)
            prop_score = await self._scorer.score_document(proposed, benchmark, model=model)

            if self.accept_reject(cur_score.aggregate, prop_score.aggregate):
                current = proposed
                cur_score = prop_score
                accepted += 1
            else:
                rejected += 1
            history.append(cur_score.aggregate)

        return MLTResult(
            final_document=current,
            score_history=history,
            accepted=accepted,
            rejected=rejected,
            total_iterations=iterations,
            final_score=cur_score,
        )
