"""Next Event Estimation with real reference retrieval and shadow ray.

.. deprecated::
    This module is **not used** by the pipeline.
    - Shadow ray is now handled by ``engine.scorer.Scorer.shadow_ray_visual``
      with stricter calibrated prompts and ``EnsembleScorer`` aggregation.
    - Reference-grounded generation is handled by the CHANNEL_ANCHORED MIS
      channel in ``engine.mood_generator``.

    The ``NEEAgent.shadow_ray`` here uses an older, lenient prompt that does
    not match the current pipeline's strict scoring standards.
    Kept for reference only — do not import.

NEE directly connects to "point light sources" — known-good reference
material — instead of hoping random sampling finds the right answer.
The shadow ray performs a real consistency check whose result feeds back
into the Russian Roulette decision.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from adapters.base import LLMAdapter
from .benchmark import Benchmark


# ---------------------------------------------------------------------------
# Reference store
# ---------------------------------------------------------------------------


class ReferenceStore(BaseModel):
    """Collected reference material from backward-path analysis."""

    style_anchors: list[str] = Field(default_factory=list)
    structural_patterns: list[str] = Field(default_factory=list)
    reference_summaries: list[str] = Field(default_factory=list)
    raw_excerpts: list[str] = Field(default_factory=list)

    @classmethod
    def from_benchmark(cls, benchmark: Benchmark) -> ReferenceStore:
        return cls(
            style_anchors=benchmark.style_anchors,
            structural_patterns=benchmark.structural_patterns,
            reference_summaries=benchmark.reference_summaries,
        )

    def top_references(self, n: int = 5) -> list[str]:
        refs = self.reference_summaries + self.raw_excerpts
        return refs[:n]


# ---------------------------------------------------------------------------
# NEE result models
# ---------------------------------------------------------------------------


class NEEResult(BaseModel):
    content: str
    references_used: list[str] = Field(default_factory=list)
    cost: float = 0.0


class ShadowRayResult(BaseModel):
    visible: bool = True
    occlusion_reasons: list[str] = Field(default_factory=list)
    aligned_dimensions: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# NEE Agent
# ---------------------------------------------------------------------------


class NEEAgent:
    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    async def direct_sample(
        self,
        task: str,
        store: ReferenceStore,
        model: str | None = None,
    ) -> NEEResult:
        """Generate grounded output using reference material (point light sampling).

        Instead of hoping the LLM randomly produces the right answer,
        we directly inject reference knowledge into the prompt.
        """
        refs = store.top_references(5)
        if not refs:
            resp = await self._llm.generate(
                task, temperature=0.6, max_tokens=2048, model=model
            )
            return NEEResult(content=resp.content, cost=resp.cost)

        refs_block = "\n\n".join(
            f"[Reference {i + 1}]\n{r[:1500]}" for i, r in enumerate(refs)
        )
        system = (
            "You are writing a creative specification grounded in reference material. "
            "Align your output with the provided references as closely as possible — "
            "treat them as authoritative point-light sources."
        )
        if store.style_anchors:
            system += (
                "\n\nStyle anchors to honor: "
                + "; ".join(store.style_anchors[:6])
            )

        prompt = (
            f"Task:\n{task}\n\n"
            f"Reference knowledge (use these as grounding):\n{refs_block}"
        )
        resp = await self._llm.generate(
            prompt,
            system=system,
            temperature=0.5,
            max_tokens=2048,
            model=model,
        )
        return NEEResult(
            content=resp.content,
            references_used=[r[:200] for r in refs],
            cost=resp.cost,
        )

    async def shadow_ray(
        self,
        candidate: str,
        context: str,
        benchmark: Benchmark,
        model: str | None = None,
    ) -> ShadowRayResult:
        """Check whether the candidate is consistent with context and style.

        Returns a structured result that feeds into the RR decision.
        Occluded samples get penalized by RR (lower survival probability).
        """
        style_block = ", ".join(benchmark.style_anchors[:8]) if benchmark.style_anchors else "(none)"

        prompt = (
            "Consistency audit (shadow ray visibility test).\n\n"
            f"Context / brief:\n{context[:2000]}\n\n"
            f"Style requirements: {style_block}\n\n"
            f"Candidate:\n---\n{candidate[:3000]}\n---\n\n"
            "Check for:\n"
            "1. Factual/logical contradictions with the context\n"
            "2. Style violations\n"
            "3. Missing critical elements\n\n"
            'Respond with JSON: {"visible": true/false, '
            '"occlusion_reasons": [...], "aligned_dimensions": [...]}'
        )
        resp = await self._llm.generate(
            prompt,
            system="You are a consistency auditor. Respond with JSON only.",
            temperature=0.1,
            max_tokens=512,
            model=model,
        )

        import json
        try:
            cleaned = resp.content.strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start >= 0 and end > start:
                data = json.loads(cleaned[start : end + 1])
            else:
                data = json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            return ShadowRayResult(visible=True)

        return ShadowRayResult(
            visible=bool(data.get("visible", True)),
            occlusion_reasons=data.get("occlusion_reasons", []),
            aligned_dimensions=data.get("aligned_dimensions", []),
        )
