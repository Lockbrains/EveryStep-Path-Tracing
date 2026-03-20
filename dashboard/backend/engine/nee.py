from __future__ import annotations

from pydantic import BaseModel, Field

from adapters.base import LLMAdapter


class NEEResult(BaseModel):
    content: str
    references_used: list[str] = Field(default_factory=list)
    cost: float = 0.0


class NEEAgent:
    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    async def direct_sample(
        self,
        task: str,
        reference_sources: list[str],
        model: str | None = None,
    ) -> NEEResult:
        refs = "\n".join(f"[ref {i+1}] {r}" for i, r in enumerate(reference_sources))
        system = (
            "Next-event style grounding: align output with the provided reference strings "
            "as if connecting to point light sources."
        )
        prompt = f"Task:\n{task}\n\nReference knowledge:\n{refs}"
        resp = await self._llm.generate(
            prompt,
            system=system,
            temperature=0.5,
            max_tokens=2048,
            model=model,
        )
        return NEEResult(
            content=resp.content,
            references_used=list(reference_sources),
            cost=resp.cost,
        )

    async def shadow_ray(
        self,
        candidate: str,
        context: str,
        model: str | None = None,
    ) -> bool:
        prompt = (
            "Visibility test (shadow ray): is the candidate consistent with the context?\n"
            f"Context:\n{context}\n\nCandidate:\n{candidate}\n\n"
            "Reply with exactly one word: VISIBLE or OCCLUDED"
        )
        resp = await self._llm.generate(
            prompt,
            system="Answer with one word only.",
            temperature=0.0,
            max_tokens=8,
            model=model,
        )
        t = resp.content.strip().upper()
        return "VISIBLE" in t and "OCCLUDED" not in t
