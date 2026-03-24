"""Art Bible generation pipeline using real Monte Carlo variance reduction.

Complete flow:
1. Backward path: analyze references -> benchmark (dimensions, style, structure)
2. For each step: generate mood board candidates (images + annotation)
   -> score ALL visually -> diversity penalty -> shadow ray top-K
   -> select best consistent candidate -> Russian Roulette (terminate -> retry)
   -> RR weight accumulates into path throughput
   -> extract feedback for next step, pass images as context
3. Optional MLT refinement pass on annotations
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import AsyncIterator, Callable, Literal

from pydantic import BaseModel, Field

from adapters.base import ImageInput, LLMAdapter
from engine.benchmark import (
    Benchmark,
    BenchmarkAnalyzer,
    StepCriteria,
    StepDefinition,
)
from engine.feedback import (
    FeedbackExtractor,
    PromptBuilder,
    StructuredFeedback,
)
from engine.mood_board import MoodBoard
from engine.mood_generator import MoodBoardGenerator
from engine.rr import RussianRoulette
from engine.diversity import apply_diversity_penalty
from engine.mlt import MLTEngine
from engine.scorer import EnsembleScorer, MultiDimScore, Scorer

DEFAULT_STEPS: list[StepDefinition] = [
    StepDefinition(index=0, title="Worldview & Setting", description="Core world concept, lore foundations, and thematic pillars"),
    StepDefinition(index=1, title="Color Palette & Visual Tone", description="Primary/secondary/accent colors, mood, lighting direction"),
    StepDefinition(index=2, title="Material & Texture Specifications", description="Surface materials, texture styles, shader guidelines"),
    StepDefinition(index=3, title="Character Design Guidelines", description="Silhouettes, proportions, costume language, faction differentiation"),
    StepDefinition(index=4, title="Environment & Architecture Rules", description="Structural motifs, scale language, biome-specific rules"),
]

EventType = Literal[
    "benchmark_start",
    "benchmark_complete",
    "step_start",
    "sample_generated",
    "scoring_complete",
    "shadow_ray",
    "rr_decision",
    "step_retry",
    "step_complete",
    "mlt_start",
    "mlt_iteration",
    "mlt_complete",
    "path_complete",
]

STRATEGY_ESCALATION = {
    "naive": "importance",
    "importance": "mis",
    "mis": "mis",
}
SHADOW_RAY_TOP_K = 3


class PipelineEvent(BaseModel):
    event_type: EventType
    step: int
    data: dict = Field(default_factory=dict)
    timestamp: str


class ArtBibleConfig(BaseModel):
    brief: str
    references: list[str] = Field(default_factory=list)
    image_refs: list[str] = Field(default_factory=list)
    n_samples: int = 3
    strategies: list[str] = Field(default_factory=lambda: ["naive"])
    model: str | None = None
    rr_threshold: float = 0.55
    max_retries: int = 2
    use_mlt: bool = False
    mlt_iterations: int = 10
    steps: list[dict] | None = None


ImageStoreFn = Callable[[str, str, str], str]


def _utc_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def _escalate_strategy(current: str, attempt: int) -> str:
    """Escalate sampling strategy on retry.

    attempt 0 -> user's chosen strategy
    attempt 1 -> next level in chain
    attempt 2+ -> forced 'mis' (uses all channels including guided)
    """
    if attempt == 0:
        return current
    if attempt >= 2:
        return "mis"
    return STRATEGY_ESCALATION.get(current, "mis")


class ArtBiblePipeline:
    def __init__(
        self,
        llm: LLMAdapter,
        image_store_fn: ImageStoreFn | None = None,
        scoring_llms: list[LLMAdapter] | None = None,
    ) -> None:
        self._llm = llm
        self._analyzer = BenchmarkAnalyzer(llm)
        self._rr = RussianRoulette()
        self._image_store_fn = image_store_fn

        if scoring_llms and len(scoring_llms) > 1:
            self._ensemble = EnsembleScorer(scoring_llms, adversarial=True)
            self._scorer = self._ensemble.primary_scorer
        else:
            judge = (scoring_llms[0] if scoring_llms else llm)
            self._scorer = Scorer(judge, adversarial=True)
            self._ensemble = EnsembleScorer([judge], adversarial=True)

        def _store_fn(data: str, mime: str, fname: str) -> str:
            if image_store_fn:
                return image_store_fn(data, mime, fname)
            import uuid as _uuid
            return str(_uuid.uuid4())

        self._mood_gen = MoodBoardGenerator(llm, image_store_fn=_store_fn)

    def _get_steps(self, config: ArtBibleConfig) -> list[StepDefinition]:
        if config.steps:
            return [
                StepDefinition(
                    index=i,
                    title=s.get("title", f"Step {i+1}"),
                    description=s.get("description", ""),
                )
                for i, s in enumerate(config.steps)
            ]
        return DEFAULT_STEPS

    def _primary_strategy(self, config: ArtBibleConfig) -> str:
        return (config.strategies[0] if config.strategies else "naive").lower()

    async def _shadow_ray_select(
        self,
        candidates: list[MoodBoard],
        all_scores: list[MultiDimScore],
        ref_images: list[ImageInput] | None,
        benchmark: Benchmark,
        context: str,
        model: str | None,
    ) -> tuple[int, MoodBoard, MultiDimScore, bool, list[str], float]:
        """Shadow ray on top-K candidates, return best consistent one.

        Returns (index, board, score, visible, reasons, alignment).
        Falls back to the highest-scoring candidate if none pass shadow ray.
        """
        ranked = sorted(
            range(len(all_scores)),
            key=lambda i: all_scores[i].aggregate,
            reverse=True,
        )
        top_k = ranked[:min(SHADOW_RAY_TOP_K, len(ranked))]

        best_consistent_idx = -1
        best_consistent_alignment = -1.0
        fallback_idx = top_k[0]
        fallback_visible = False
        fallback_reasons: list[str] = []
        fallback_alignment = 0.0

        for rank, idx in enumerate(top_k):
            visible, reasons, alignment = (
                await self._ensemble.shadow_ray_visual(
                    candidates[idx], ref_images, benchmark,
                    context=context, model=model,
                )
            )
            all_scores[idx].shadow_visible = visible
            all_scores[idx].shadow_alignment = alignment
            all_scores[idx].occlusion_reasons = reasons

            if rank == 0:
                fallback_visible = visible
                fallback_reasons = reasons
                fallback_alignment = alignment

            if visible and alignment > best_consistent_alignment:
                best_consistent_idx = idx
                best_consistent_alignment = alignment

        if best_consistent_idx >= 0:
            idx = best_consistent_idx
            sc = all_scores[idx]
            return idx, candidates[idx], sc, sc.shadow_visible, sc.occlusion_reasons, sc.shadow_alignment

        idx = fallback_idx
        sc = all_scores[idx]
        return idx, candidates[idx], sc, fallback_visible, fallback_reasons, fallback_alignment

    async def run(
        self,
        brief: str,
        config: ArtBibleConfig,
        image_data: list[tuple[str, str]] | None = None,
    ) -> AsyncIterator[PipelineEvent]:
        steps = self._get_steps(config)

        ref_images: list[ImageInput] | None = None
        if image_data:
            ref_images = [
                ImageInput(data=b64, mime_type=mime)
                for b64, mime in image_data
            ]

        # --- Backward path: analyze references ---
        yield PipelineEvent(
            event_type="benchmark_start", step=0,
            data={
                "n_references": len(config.references),
                "n_images": len(image_data or []),
            },
            timestamp=_utc_ts(),
        )
        benchmark = await self._analyzer.analyze_references(
            config.references, brief,
            model=config.model,
            images=ref_images,
        )
        yield PipelineEvent(
            event_type="benchmark_complete", step=0,
            data={
                "n_dimensions": len(benchmark.dimensions),
                "dimensions": [d.model_dump() for d in benchmark.dimensions],
                "style_anchors": benchmark.style_anchors,
                "style_exclusions": benchmark.style_exclusions,
                "structural_patterns": benchmark.structural_patterns,
                "reference_summaries": benchmark.reference_summaries,
            },
            timestamp=_utc_ts(),
        )

        boards: list[MoodBoard] = []
        path_scores: list[float] = []
        path_throughput = 1.0
        feedback: StructuredFeedback | None = None
        base_strategy = self._primary_strategy(config)

        # --- Forward path: step-by-step mood board generation ---
        for step_def in steps:
            step_num = step_def.index + 1

            criteria = await self._analyzer.derive_step_criteria(
                benchmark, step_def, total_steps=len(steps), model=config.model
            )

            step_context = (
                f"CURRENT STEP: {step_def.title}\n"
                f"Step description: {step_def.description or step_def.title}\n"
                f"Step {step_def.index + 1} of {len(steps)}\n\n"
                f"The candidate MUST primarily address this step's topic. "
                f"A candidate that matches overall style but does not focus on "
                f"'{step_def.title}' should score lower than one that directly "
                f"addresses the step topic.\n\n"
                f"Overall brief: {brief}"
            )

            yield PipelineEvent(
                event_type="step_start", step=step_num,
                data={
                    "title": step_def.title,
                    "n_dimensions": len(criteria.dimensions),
                    "strategy": base_strategy,
                    "path_throughput": path_throughput,
                },
                timestamp=_utc_ts(),
            )

            best_board: MoodBoard | None = None
            best_score: MultiDimScore | None = None
            step_weight = 1.0
            attempt = 0

            while attempt <= config.max_retries:
                step_strategy = _escalate_strategy(base_strategy, attempt)

                candidates = await self._mood_gen.sample_candidates(
                    n=config.n_samples,
                    step=step_def,
                    brief=brief,
                    prior_boards=boards,
                    feedback=feedback,
                    benchmark=benchmark,
                    ref_images=ref_images,
                    strategy=step_strategy,
                    model=config.model,
                )

                for i, cand in enumerate(candidates):
                    yield PipelineEvent(
                        event_type="sample_generated", step=step_num,
                        data={
                            "candidate_index": i,
                            "annotation": cand.annotation[:500],
                            "n_images": len(cand.images),
                            "image_ids": cand.image_ids,
                            "strategy": cand.strategy or step_strategy,
                        },
                        timestamp=_utc_ts(),
                    )

                all_scores: list[MultiDimScore] = []
                for cand in candidates:
                    s = await self._ensemble.score_mood_board(
                        cand, criteria, context=step_context,
                        prior_boards=boards, model=config.model,
                    )
                    all_scores.append(s)

                if len(candidates) > 1:
                    apply_diversity_penalty(candidates, all_scores)

                yield PipelineEvent(
                    event_type="scoring_complete", step=step_num,
                    data={
                        "n_candidates": len(candidates),
                        "all_aggregates": [s.aggregate for s in all_scores],
                        "strategy": step_strategy,
                    },
                    timestamp=_utc_ts(),
                )

                # Shadow ray on top-K, select best consistent candidate
                best_idx, best_cand, best_cand_score, visible, occlusion_reasons, alignment = (
                    await self._shadow_ray_select(
                        candidates, all_scores, ref_images,
                        benchmark, step_context, config.model,
                    )
                )

                yield PipelineEvent(
                    event_type="scoring_complete", step=step_num,
                    data={
                        "n_candidates": len(candidates),
                        "best_index": best_idx,
                        "best_aggregate": best_cand_score.aggregate,
                        "best_dimensions": [
                            {"dimension": ds.dimension, "score": ds.score, "suggestion": ds.suggestion}
                            for ds in best_cand_score.dimension_scores
                        ],
                        "all_aggregates": [s.aggregate for s in all_scores],
                        "best_image_ids": best_cand.image_ids,
                        "best_strategy": best_cand.strategy or step_strategy,
                        "exclusion_violations": best_cand_score.exclusion_violations,
                    },
                    timestamp=_utc_ts(),
                )

                yield PipelineEvent(
                    event_type="shadow_ray", step=step_num,
                    data={
                        "visible": visible,
                        "alignment_score": alignment,
                        "occlusion_reasons": occlusion_reasons,
                        "checked_top_k": min(SHADOW_RAY_TOP_K, len(candidates)),
                    },
                    timestamp=_utc_ts(),
                )

                rr_result = self._rr.decide(
                    best_cand_score, config.rr_threshold,
                    criteria=criteria, shadow_visible=visible,
                    step_index=step_def.index,
                )

                yield PipelineEvent(
                    event_type="rr_decision", step=step_num,
                    data={
                        "continue": rr_result.continue_path,
                        "weight": rr_result.weight,
                        "survival_probability": rr_result.survival_probability,
                        "score": best_cand_score.aggregate,
                        "attempt": attempt,
                        "strategy_used": step_strategy,
                    },
                    timestamp=_utc_ts(),
                )

                if rr_result.continue_path:
                    best_board = best_cand
                    best_score = best_cand_score
                    step_weight = rr_result.weight
                    break

                if attempt < config.max_retries and rr_result.retry_feedback:
                    feedback = rr_result.retry_feedback
                    next_strategy = _escalate_strategy(base_strategy, attempt + 1)
                    yield PipelineEvent(
                        event_type="step_retry", step=step_num,
                        data={
                            "attempt": attempt + 1,
                            "max_retries": config.max_retries,
                            "weaknesses": feedback.weaknesses[:3],
                            "escalated_strategy": next_strategy,
                        },
                        timestamp=_utc_ts(),
                    )
                else:
                    best_board = best_cand
                    best_score = best_cand_score
                    step_weight = 1.0
                    break

                attempt += 1

            if best_board is None:
                best_board = MoodBoard(step_index=step_def.index, annotation="(empty)")

            path_throughput *= step_weight
            raw_score = best_score.aggregate if best_score else 0.0
            weighted_score = raw_score * path_throughput
            boards.append(best_board)
            path_scores.append(weighted_score)

            if best_score:
                feedback = FeedbackExtractor.extract(best_score, criteria)

            yield PipelineEvent(
                event_type="step_complete", step=step_num,
                data={
                    "annotation": best_board.annotation[:2000],
                    "score": raw_score,
                    "weighted_score": weighted_score,
                    "step_weight": step_weight,
                    "path_throughput": path_throughput,
                    "board_image_ids": best_board.image_ids,
                    "n_images": len(best_board.images),
                    "dimensions": (
                        [{"dimension": ds.dimension, "score": ds.score}
                         for ds in best_score.dimension_scores]
                        if best_score else []
                    ),
                    "attempt": attempt,
                },
                timestamp=_utc_ts(),
            )

        # --- Optional MLT refinement on annotations ---
        if config.use_mlt and boards:
            yield PipelineEvent(
                event_type="mlt_start", step=len(steps),
                data={"iterations": config.mlt_iterations},
                timestamp=_utc_ts(),
            )

            mlt = MLTEngine(self._llm, scorer=self._ensemble)
            annotations = [b.annotation for b in boards]
            mlt_result = await mlt.run(
                annotations, benchmark,
                model=config.model,
                iterations=config.mlt_iterations,
            )

            for i, refined_text in enumerate(mlt_result.final_document):
                if i < len(boards):
                    boards[i].annotation = refined_text

            if mlt_result.final_score:
                path_scores.append(mlt_result.final_score.aggregate)

            yield PipelineEvent(
                event_type="mlt_complete", step=len(steps),
                data={
                    "accepted": mlt_result.accepted,
                    "rejected": mlt_result.rejected,
                    "score_history": mlt_result.score_history,
                    "final_score": (
                        mlt_result.final_score.aggregate
                        if mlt_result.final_score else None
                    ),
                },
                timestamp=_utc_ts(),
            )

        # --- Done ---
        yield PipelineEvent(
            event_type="path_complete", step=len(steps),
            data={
                "n_steps": len(boards),
                "boards": [
                    {
                        "step_index": b.step_index,
                        "annotation": b.annotation[:2000],
                        "image_ids": b.image_ids,
                        "n_images": len(b.images),
                    }
                    for b in boards
                ],
                "path_scores": path_scores,
                "path_throughput": path_throughput,
                "benchmark_dimensions": [d.name for d in benchmark.dimensions],
            },
            timestamp=_utc_ts(),
        )
