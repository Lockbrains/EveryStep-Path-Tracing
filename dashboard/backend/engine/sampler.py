"""Monte Carlo sampler with real importance sampling and MIS.

.. deprecated::
    This module is **not used** by the pipeline. All sampling is handled by
    ``engine.mood_generator.MoodBoardGenerator`` which generates multi-modal
    candidates (images + annotation) with its own MIS channel system.

    The ``MonteCarloSampler`` here only generates text and its MIS weights
    are never consumed. Kept for reference only — do not import.

Naive sampling uses no guidance. Importance sampling injects feedback
constraints. MIS combines free / reference-grounded / constraint-guided
strategies with the balance heuristic.
"""

from __future__ import annotations

import asyncio

from pydantic import BaseModel, Field

from adapters.base import LLMAdapter, LLMResponse
from .benchmark import Benchmark
from .feedback import PromptBuilder, StructuredFeedback


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class SampleResult(BaseModel):
    content: str
    cost: float = Field(ge=0.0, default=0.0)
    strategy: str = "naive"
    tokens_in: int = 0
    tokens_out: int = 0
    metadata: dict = Field(default_factory=dict)


class SamplingConfig(BaseModel):
    temperature: float = 0.8
    max_tokens: int = 2048


# ---------------------------------------------------------------------------
# Sampler
# ---------------------------------------------------------------------------


class MonteCarloSampler:
    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    async def _gen(
        self,
        prompt: str,
        model: str | None,
        config: SamplingConfig,
        system: str | None = None,
    ) -> LLMResponse:
        return await self._llm.generate(
            prompt,
            system=system,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            model=model,
        )

    def _to_result(self, resp: LLMResponse, strategy: str, **extra: object) -> SampleResult:
        return SampleResult(
            content=resp.content,
            cost=resp.cost,
            strategy=strategy,
            tokens_in=resp.tokens_in,
            tokens_out=resp.tokens_out,
            metadata={"model": resp.model, **extra},
        )

    # -- Naive: pure random, no guidance ----------------------------------

    async def naive_sample(
        self,
        prompt: str,
        n: int,
        model: str | None = None,
        system: str | None = None,
        config: SamplingConfig | None = None,
    ) -> list[SampleResult]:
        cfg = config or SamplingConfig()
        tasks = [self._gen(prompt, model, cfg, system=system) for _ in range(n)]
        responses = await asyncio.gather(*tasks)
        return [self._to_result(r, "naive") for r in responses]

    # -- Importance sampling: feedback-guided ------------------------------

    async def importance_sample(
        self,
        prompt: str,
        n: int,
        feedback: StructuredFeedback,
        model: str | None = None,
        system: str | None = None,
        config: SamplingConfig | None = None,
    ) -> list[SampleResult]:
        """Sample with constraints injected from feedback (IS direction guide).

        The feedback weaknesses and hard_constraints are prepended to the
        system prompt, biasing the LLM toward the high-importance region
        of the output space.
        """
        cfg = config or SamplingConfig()

        constraint_block = ""
        if feedback.hard_constraints:
            constraint_block += "CONSTRAINTS:\n" + "\n".join(
                f"- {c}" for c in feedback.hard_constraints
            ) + "\n\n"
        if feedback.soft_guidance:
            constraint_block += "GUIDANCE:\n" + "\n".join(
                f"- {g}" for g in feedback.soft_guidance
            ) + "\n\n"
        if feedback.weaknesses:
            constraint_block += "ADDRESS THESE WEAKNESSES:\n" + "\n".join(
                f"- {w}" for w in feedback.weaknesses[:5]
            ) + "\n\n"

        is_system = (system or "") + "\n\n" + constraint_block if constraint_block else system

        tasks = [self._gen(prompt, model, cfg, system=is_system) for _ in range(n)]
        responses = await asyncio.gather(*tasks)
        return [
            self._to_result(r, "importance", constraints_injected=bool(constraint_block))
            for r in responses
        ]

    # -- MIS: combine multiple sampling strategies -------------------------

    async def mis_sample(
        self,
        prompt: str,
        n_free: int,
        n_ref: int,
        n_guided: int,
        feedback: StructuredFeedback | None,
        benchmark: Benchmark,
        model: str | None = None,
        system: str | None = None,
        config: SamplingConfig | None = None,
    ) -> list[SampleResult]:
        """Multiple Importance Sampling with balance heuristic.

        Three strategy channels:
        - free: no constraints (BSDF sampling analogue)
        - reference-grounded: benchmark style_anchors injected (light sampling)
        - constraint-guided: feedback injected (importance sampling)

        MIS weight for sample from strategy j:
          w_j(x) = n_j * p_j(x) / sum_k(n_k * p_k(x))

        Since we cannot compute exact PDFs for LLM outputs, we approximate
        the balance heuristic by scoring how well each sample aligns with
        each strategy's constraints (a soft PDF proxy).
        """
        cfg = config or SamplingConfig()
        all_results: list[SampleResult] = []

        ref_system = system or ""
        if benchmark.style_anchors:
            ref_system += (
                "\n\nGROUNDING REFERENCES (style anchors from analyzed references):\n"
                + "\n".join(f"- {a}" for a in benchmark.style_anchors[:8])
            )
        if benchmark.structural_patterns:
            ref_system += (
                "\n\nSTRUCTURAL PATTERNS:\n"
                + "\n".join(f"- {p}" for p in benchmark.structural_patterns[:5])
            )

        guided_system = system or ""
        if feedback and not feedback.is_empty():
            if feedback.hard_constraints:
                guided_system += "\n\nCONSTRAINTS:\n" + "\n".join(
                    f"- {c}" for c in feedback.hard_constraints
                )
            if feedback.soft_guidance:
                guided_system += "\n\nGUIDANCE:\n" + "\n".join(
                    f"- {g}" for g in feedback.soft_guidance
                )

        async def _draw(n: int, strat: str, sys: str | None) -> list[SampleResult]:
            if n <= 0:
                return []
            tasks = [self._gen(prompt, model, cfg, system=sys) for _ in range(n)]
            responses = await asyncio.gather(*tasks)
            return [self._to_result(r, f"mis_{strat}") for r in responses]

        free_samples, ref_samples, guided_samples = await asyncio.gather(
            _draw(n_free, "free", system),
            _draw(n_ref, "ref", ref_system if ref_system.strip() != (system or "").strip() else system),
            _draw(n_guided, "guided", guided_system if guided_system.strip() != (system or "").strip() else system),
        )

        n_total = n_free + n_ref + n_guided
        for samples, n_strat, strat_name in [
            (free_samples, n_free, "free"),
            (ref_samples, n_ref, "ref"),
            (guided_samples, n_guided, "guided"),
        ]:
            for s in samples:
                w = n_strat / n_total if n_total > 0 else 1.0
                s.metadata["mis_weight"] = w
                s.metadata["mis_strategy"] = strat_name
                all_results.append(s)

        return all_results
