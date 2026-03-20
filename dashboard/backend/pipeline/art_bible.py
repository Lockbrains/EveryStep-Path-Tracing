from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator, Literal

from pydantic import BaseModel, Field

from adapters.base import LLMAdapter
from engine.mlt import MLTEngine
from engine.nee import NEEAgent
from engine.sampler import MonteCarloSampler, SampleResult, SamplingConfig
from engine.validator import ValidationResult, Validator

STEP_TITLES: list[str] = [
    "Worldview & Setting",
    "Color Palette & Visual Tone",
    "Material & Texture Specifications",
    "Character Design Guidelines",
    "Environment & Architecture Rules",
]

EventType = Literal[
    "step_start",
    "sample_generated",
    "validation",
    "rr_decision",
    "step_complete",
    "path_complete",
]


class PipelineEvent(BaseModel):
    event_type: EventType
    step: int
    data: dict = Field(default_factory=dict)
    timestamp: str


class ArtBibleConfig(BaseModel):
    brief: str
    n_samples: int = 3
    strategies: list[str] = Field(default_factory=lambda: ["naive"])
    model: str | None = None
    rr_threshold: float = 0.4
    use_mlt: bool = False
    mlt_iterations: int = 20
    mis_n_free: int | None = None
    mis_n_rag: int | None = None
    mis_n_tool: int | None = None


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


class ArtBiblePipeline:
    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    def _primary_strategy(self, config: ArtBibleConfig) -> str:
        return (config.strategies[0] if config.strategies else "naive").lower()

    async def _sample_step(
        self,
        task: str,
        config: ArtBibleConfig,
        brief: str,
    ) -> list[SampleResult]:
        primary = self._primary_strategy(config)
        sampler = MonteCarloSampler(self._llm)
        scfg = SamplingConfig()
        if primary == "nee":
            nee = NEEAgent(self._llm)
            refs = [brief[:800], "Reference: cohesive visual lore and readable silhouettes."]
            nee_out = await nee.direct_sample(task, refs, model=config.model)
            q = max(0.0, min(1.0, len(nee_out.content) / 2500.0))
            return [
                SampleResult(
                    content=nee_out.content,
                    quality_score=q,
                    cost=nee_out.cost,
                    strategy="nee",
                    metadata={"references": nee_out.references_used},
                )
            ]
        if primary == "mis":
            n = max(1, config.n_samples)
            nf = config.mis_n_free or max(1, n // 3)
            nr = config.mis_n_rag or max(1, n // 3)
            nt = config.mis_n_tool or max(1, n - nf - nr)
            return await sampler.mis_sample(
                task, nf, nr, nt, config.model, config=scfg
            )
        if primary == "importance":
            cons = [brief[:400], "Maintain internal consistency with prior sections."]
            return await sampler.importance_sample(
                task, config.n_samples, config.model, cons, config=scfg
            )
        return await sampler.naive_sample(
            task, config.n_samples, config.model, config=scfg
        )

    async def run(
        self,
        brief: str,
        config: ArtBibleConfig,
    ) -> AsyncIterator[PipelineEvent]:
        validator = Validator(self._llm)
        nee = NEEAgent(self._llm)
        mlt = MLTEngine(self._llm)
        sections: list[str] = []
        path_scores: list[float] = []

        for step_idx, title in enumerate(STEP_TITLES):
            step_num = step_idx + 1
            yield PipelineEvent(
                event_type="step_start",
                step=step_num,
                data={"title": title},
                timestamp=_utc_ts(),
            )
            prior = "\n\n".join(sections) if sections else "(none)"
            task = f"{title}\n\nCreative brief:\n{brief}\n\nPrior sections:\n{prior}"
            samples = await self._sample_step(task, config, brief)
            for s in samples:
                yield PipelineEvent(
                    event_type="sample_generated",
                    step=step_num,
                    data=s.model_dump(),
                    timestamp=_utc_ts(),
                )
            best = max(samples, key=lambda x: x.quality_score)
            visible = await nee.shadow_ray(best.content, brief, model=config.model)
            score = await validator.score(
                best.content,
                context=brief,
                criteria=[title, "alignment with brief"],
                model=config.model,
            )
            cont, weight = validator.russian_roulette(score, config.rr_threshold)
            vr = ValidationResult(
                score=score,
                should_continue=cont,
                weight=weight,
                reasoning="occluded" if not visible else "visible",
            )
            yield PipelineEvent(
                event_type="validation",
                step=step_num,
                data=vr.model_dump(),
                timestamp=_utc_ts(),
            )
            yield PipelineEvent(
                event_type="rr_decision",
                step=step_num,
                data={"continue": cont, "weight": weight, "score": score},
                timestamp=_utc_ts(),
            )
            sections.append(best.content)
            path_scores.append(score)
            yield PipelineEvent(
                event_type="step_complete",
                step=step_num,
                data={"section": best.content, "score": score},
                timestamp=_utc_ts(),
            )

        mlt_summary: dict | None = None
        if config.use_mlt:
            mlt_task = f"{brief}\n\nSections:\n" + "\n---\n".join(sections)
            mlt_res = await mlt.run(
                mlt_task,
                config.model,
                iterations=config.mlt_iterations,
                criteria=["global consistency", "visual clarity"],
            )
            sections = mlt_res.final_document
            mlt_summary = mlt_res.model_dump()

        yield PipelineEvent(
            event_type="path_complete",
            step=len(STEP_TITLES),
            data={
                "sections": sections,
                "path_scores": path_scores,
                "mlt": mlt_summary,
            },
            timestamp=_utc_ts(),
        )
