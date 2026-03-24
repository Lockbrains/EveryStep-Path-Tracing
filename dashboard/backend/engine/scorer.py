"""Multi-dimensional LLM-as-judge scorer with calibrated rubrics.

Replaces quality.py and validator.py with structured, per-dimension scoring.
Each candidate is evaluated on every dimension from the benchmark, producing
actionable feedback (not just a single float).

Scoring is deliberately strict: average work should land around 0.5, and
scores above 0.8 are reserved for genuinely excellent output.  An optional
adversarial pass double-checks scores from a fault-finding perspective.
"""

from __future__ import annotations

import asyncio
import json
import logging

from pydantic import BaseModel, Field

from adapters.base import ImageInput, LLMAdapter
from .benchmark import Benchmark, QualityDimension, StepCriteria
from .mood_board import MoodBoard

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class DimensionScore(BaseModel):
    dimension: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""
    suggestion: str = ""


class MultiDimScore(BaseModel):
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    aggregate: float = Field(ge=0.0, le=1.0, default=0.0)
    shadow_visible: bool = True
    shadow_alignment: float = Field(ge=0.0, le=1.0, default=1.0)
    occlusion_reasons: list[str] = Field(default_factory=list)
    exclusion_violations: list[str] = Field(default_factory=list)

    def weakest_dimensions(self, n: int = 3) -> list[DimensionScore]:
        return sorted(self.dimension_scores, key=lambda d: d.score)[:n]

    def strongest_dimensions(self, n: int = 3) -> list[DimensionScore]:
        return sorted(self.dimension_scores, key=lambda d: d.score, reverse=True)[:n]


class ScoredCandidate(BaseModel):
    index: int
    content: str
    score: MultiDimScore
    strategy: str = ""
    cost: float = 0.0


# ---------------------------------------------------------------------------
# Prompts — calibrated with strict anchors
# ---------------------------------------------------------------------------

_SCORE_SYSTEM = (
    "You are a precise and fair quality evaluator. "
    "Score each dimension based on how well the candidate meets its specific "
    "requirements. Be honest — reward genuine quality, penalise real flaws. "
    "Always respond with valid JSON only — no markdown fences, no commentary."
)

_SCORE_PROMPT = """\
Evaluate this candidate output against the following quality dimensions.
Use the CALIBRATED SCORING SCALE below.
{exclusions_block}
STEP RELEVANCE PRIORITY: The Context below specifies a CURRENT STEP with a
specific topic. A candidate MUST directly and primarily address that step's
topic. A candidate that merely matches overall style or theme but does NOT
focus on the step's specific topic (e.g. "Color Palette" step should show
actual color palettes, swatches, or color analysis — not just stylistically
nice images) must be penalised on ALL dimensions. Step relevance is a
prerequisite for a high score, not a bonus.

CALIBRATED SCORING SCALE:
  0.0 – 0.2 : Fundamentally broken, off-topic, or ignores the step topic.
  0.2 – 0.4 : Poor. Does not address the step topic, or has significant flaws.
  0.4 – 0.55: Below average. Partially addresses step topic but has clear gaps.
  0.55 – 0.7 : Solid. Addresses the step topic adequately with room to improve.
  0.7 – 0.85: Good. Directly addresses step topic with identifiable strengths.
  0.85 – 1.0 : Excellent. Outstanding step-specific output — reserve for genuinely impressive work.

A candidate that faithfully addresses both the step topic AND the brief should
score 0.55-0.7. Only penalise for actual deficiencies, not for stylistic preferences.

Dimensions to evaluate:
{dimensions_block}

Context / brief:
{context}

Candidate to evaluate:
---
{candidate}
---

For each dimension, provide:
- "dimension": the dimension name (must match exactly)
- "score": float 0.0–1.0 following the calibrated scale above
- "reasoning": 1-2 sentences justifying the score with specific evidence
- "suggestion": concrete improvement action (empty string ONLY if score >= 0.85)

Also check for FORBIDDEN element violations and include:
- "exclusion_violations": list of specific forbidden elements found (empty list if none)

Respond with a JSON object:
{{"scores": [...], "exclusion_violations": [...]}}"""

_ADVERSARIAL_SYSTEM = (
    "You are a critical quality auditor whose job is to find flaws. "
    "You ALWAYS look for what is wrong, weak, or missing. "
    "You penalize vagueness, inconsistency, and mediocrity. "
    "Respond with valid JSON only."
)

_ADVERSARIAL_PROMPT = """\
You are re-scoring a candidate that was previously evaluated. Your job is to
be MORE CRITICAL than the first pass. Look specifically for:
- Weaknesses that were overlooked
- Scores that seem inflated relative to actual quality
- Vague or generic content that lacks specificity
- Inconsistencies with the brief or prior context

{original_prompt}"""

_SHADOW_SYSTEM = (
    "You are a consistency auditor verifying that a candidate aligns with "
    "its reference context. Be fair — only flag genuine inconsistencies, "
    "not stylistic differences or creative interpretation. "
    "Respond with valid JSON only."
)

_SHADOW_PROMPT = """\
Reference context:
{context}

Style requirements:
{style_constraints}
{exclusions_block}
Candidate:
---
{candidate}
---

Verify alignment in these areas (score each 0.0–1.0):

0. EXCLUSION COMPLIANCE (HIGHEST PRIORITY): Does the candidate contain ANY of
   the FORBIDDEN elements listed above? If ANY forbidden element is present,
   alignment_score MUST be <= 0.3 and visible MUST be false, regardless of
   all other checks. List every violation found.

1. COLOR CONSISTENCY: Do palettes and lighting broadly match the references?
2. STYLE UNITY: Is the visual language consistent with the reference style?
3. SPATIAL LOGIC: Are proportions and composition coherent?
4. THEMATIC COHERENCE: Does the content fit the established narrative/mood?
5. TECHNICAL QUALITY: Are there significant artifacts or quality issues?

Only flag issues that represent genuine inconsistencies with the references.
Creative interpretation within the established style is acceptable.

Respond with:
{{
  "alignment_score": <float 0.0-1.0, overall consistency>,
  "visible": <true if alignment_score >= 0.5 AND no exclusion violations>,
  "exclusion_violations": ["specific forbidden element found", ...],
  "checks": {{
    "exclusion_compliance": <float, 0.0 if any violation>,
    "color_consistency": <float>,
    "style_unity": <float>,
    "spatial_logic": <float>,
    "thematic_coherence": <float>,
    "technical_quality": <float>
  }},
  "occlusion_reasons": ["specific issue 1", ...],
  "aligned_dimensions": ["dim1", ...]
}}"""


# ---------------------------------------------------------------------------
# Scorer
# ---------------------------------------------------------------------------


EXCLUSION_PENALTY_CAP = 0.3


def _exclusions_block(exclusions: list[str]) -> str:
    if not exclusions:
        return ""
    items = "\n".join(f"  - {e}" for e in exclusions)
    return (
        "\n!! FORBIDDEN ELEMENTS — if ANY of these appear in the candidate, "
        "it is a CRITICAL FAILURE regardless of other qualities. "
        "Cap ALL dimension scores at 0.3 if any violation is found:\n"
        f"{items}\n"
    )


def _dims_block(dims: list[QualityDimension]) -> str:
    lines = []
    for d in dims:
        lines.append(
            f"- {d.name} (weight={d.weight:.2f}): {d.description}\n"
            f"  low: {d.rubric_low}\n"
            f"  high: {d.rubric_high}"
        )
    return "\n".join(lines)


def _parse_json(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {}


def _weighted_aggregate(scores: list[DimensionScore], dims: list[QualityDimension]) -> float:
    weight_map = {d.name: d.weight for d in dims}
    total_w = 0.0
    total_s = 0.0
    for ds in scores:
        w = weight_map.get(ds.dimension, 0.5)
        total_w += w
        total_s += w * ds.score
    return total_s / total_w if total_w > 0 else 0.0


class Scorer:
    def __init__(self, llm: LLMAdapter, *, adversarial: bool = True) -> None:
        self._llm = llm
        self._adversarial = adversarial

    def _parse_dim_scores(
        self, data: dict, criteria: StepCriteria,
    ) -> list[DimensionScore]:
        dim_scores: list[DimensionScore] = []
        for s in data.get("scores", []):
            try:
                dim_scores.append(DimensionScore(
                    dimension=s["dimension"],
                    score=max(0.0, min(1.0, float(s.get("score", 0.5)))),
                    reasoning=s.get("reasoning", ""),
                    suggestion=s.get("suggestion", ""),
                ))
            except (KeyError, TypeError, ValueError):
                continue

        if not dim_scores:
            dim_scores = [
                DimensionScore(
                    dimension=d.name, score=0.4,
                    reasoning="Parse failure — defaulting to below-average",
                )
                for d in criteria.dimensions
            ]
        return dim_scores

    @staticmethod
    def _merge_adversarial(
        base: list[DimensionScore],
        adversarial: list[DimensionScore],
    ) -> list[DimensionScore]:
        """Merge base and adversarial scores.

        Only penalise when the adversarial scorer disagrees significantly
        (gap > 0.15). Small discrepancies are treated as scoring noise.
        When a real gap is detected the final score is the simple average
        of the two passes — not biased toward the lower value.
        """
        adv_map = {ds.dimension: ds for ds in adversarial}
        merged: list[DimensionScore] = []
        for ds in base:
            adv = adv_map.get(ds.dimension)
            if adv is None:
                merged.append(ds)
                continue
            gap = ds.score - adv.score
            if gap > 0.15:
                blended = (ds.score + adv.score) / 2.0
            else:
                blended = ds.score
            reasoning = ds.reasoning
            if adv.score < ds.score - 0.15:
                reasoning = f"{ds.reasoning} [Adversarial: {adv.reasoning}]"
            suggestion = adv.suggestion if (adv.score < ds.score - 0.15) else ds.suggestion
            merged.append(DimensionScore(
                dimension=ds.dimension,
                score=round(blended, 4),
                reasoning=reasoning,
                suggestion=suggestion or "",
            ))
        return merged

    async def score_candidate(
        self,
        content: str,
        criteria: StepCriteria,
        context: str = "",
        model: str | None = None,
    ) -> MultiDimScore:
        base_prompt = _SCORE_PROMPT.format(
            exclusions_block=_exclusions_block(criteria.style_exclusions),
            dimensions_block=_dims_block(criteria.dimensions),
            context=context or "(none)",
            candidate=content[:4000],
        )

        base_resp = await self._llm.generate(
            base_prompt, system=_SCORE_SYSTEM,
            temperature=0.2, max_tokens=2048, model=model,
        )
        data = _parse_json(base_resp.content)
        base_scores = self._parse_dim_scores(data, criteria)
        violations = [str(v) for v in data.get("exclusion_violations", [])]

        if self._adversarial:
            adv_prompt = _ADVERSARIAL_PROMPT.format(original_prompt=base_prompt)
            adv_resp = await self._llm.generate(
                adv_prompt, system=_ADVERSARIAL_SYSTEM,
                temperature=0.15, max_tokens=2048, model=model,
            )
            adv_data = _parse_json(adv_resp.content)
            adv_scores = self._parse_dim_scores(adv_data, criteria)
            for v in adv_data.get("exclusion_violations", []):
                sv = str(v)
                if sv not in violations:
                    violations.append(sv)
            base_scores = self._merge_adversarial(base_scores, adv_scores)

        agg = _weighted_aggregate(base_scores, criteria.dimensions)
        if violations:
            agg = min(agg, EXCLUSION_PENALTY_CAP)
        return MultiDimScore(
            dimension_scores=base_scores,
            aggregate=agg,
            exclusion_violations=violations,
        )

    async def score_all_candidates(
        self,
        candidates: list[str],
        criteria: StepCriteria,
        context: str = "",
        model: str | None = None,
    ) -> list[MultiDimScore]:
        tasks = [
            self.score_candidate(c, criteria, context, model)
            for c in candidates
        ]
        return await asyncio.gather(*tasks)

    async def shadow_ray(
        self,
        candidate: str,
        context: str,
        benchmark: Benchmark,
        model: str | None = None,
    ) -> tuple[bool, list[str], float]:
        """Returns (visible, occlusion_reasons, alignment_score)."""
        prompt = _SHADOW_PROMPT.format(
            context=context[:2000],
            style_constraints=json.dumps(benchmark.style_anchors[:10]),
            exclusions_block=_exclusions_block(benchmark.style_exclusions),
            candidate=candidate[:3000],
        )
        resp = await self._llm.generate(
            prompt, system=_SHADOW_SYSTEM,
            temperature=0.1, max_tokens=1024, model=model,
        )
        data = _parse_json(resp.content)
        alignment = float(data.get("alignment_score", 0.6))
        alignment = max(0.0, min(1.0, alignment))
        excl_violations = data.get("exclusion_violations", [])
        if excl_violations:
            alignment = min(alignment, EXCLUSION_PENALTY_CAP)
        visible = alignment >= 0.5 and data.get("visible", True)
        reasons = data.get("occlusion_reasons", [])
        return bool(visible), list(reasons), alignment

    def rank_candidates(
        self, scored: list[ScoredCandidate],
    ) -> list[ScoredCandidate]:
        return sorted(scored, key=lambda x: x.score.aggregate, reverse=True)

    async def score_mood_board(
        self,
        board: MoodBoard,
        criteria: StepCriteria,
        context: str = "",
        prior_boards: list[MoodBoard] | None = None,
        model: str | None = None,
    ) -> MultiDimScore:
        """Score a mood board with calibrated rubrics + adversarial pass."""
        text_content = board.annotation
        if not text_content:
            text_content = "(mood board with images, no annotation)"

        imgs: list[ImageInput] = []
        for gi in board.images[:4]:
            imgs.append(ImageInput(data=gi.data, mime_type=gi.mime_type))

        if prior_boards:
            for pb in prior_boards[-2:]:
                if pb.images:
                    imgs.append(ImageInput(
                        data=pb.images[0].data,
                        mime_type=pb.images[0].mime_type,
                    ))

        base_prompt = _SCORE_PROMPT.format(
            exclusions_block=_exclusions_block(criteria.style_exclusions),
            dimensions_block=_dims_block(criteria.dimensions),
            context=context or "(none)",
            candidate=text_content[:4000],
        )
        base_prompt += (
            "\n\nThe candidate mood board images are attached. "
            "Score them on the visual dimensions (composition, color, "
            "style consistency, etc.) as well. "
            "IMPORTANT: Check images carefully for FORBIDDEN elements."
        )
        if prior_boards:
            base_prompt += (
                "\nPrior step images are also attached for consistency checking."
            )

        all_violations: list[str] = []

        async def _run_pass(system: str, prompt: str, temp: float) -> list[DimensionScore]:
            resp = await self._llm.generate(
                prompt, system=system, temperature=temp,
                max_tokens=2048, model=model,
                images=imgs if imgs else None,
            )
            data = _parse_json(resp.content)
            for v in data.get("exclusion_violations", []):
                sv = str(v)
                if sv not in all_violations:
                    all_violations.append(sv)
            return self._parse_dim_scores(data, criteria)

        if self._adversarial:
            adv_prompt = _ADVERSARIAL_PROMPT.format(original_prompt=base_prompt)
            base_scores, adv_scores = await asyncio.gather(
                _run_pass(_SCORE_SYSTEM, base_prompt, 0.2),
                _run_pass(_ADVERSARIAL_SYSTEM, adv_prompt, 0.15),
            )
            merged = self._merge_adversarial(base_scores, adv_scores)
        else:
            merged = await _run_pass(_SCORE_SYSTEM, base_prompt, 0.2)

        agg = _weighted_aggregate(merged, criteria.dimensions)
        if all_violations:
            agg = min(agg, EXCLUSION_PENALTY_CAP)
        return MultiDimScore(
            dimension_scores=merged,
            aggregate=agg,
            exclusion_violations=all_violations,
        )

    async def shadow_ray_visual(
        self,
        board: MoodBoard,
        ref_images: list[ImageInput] | None,
        benchmark: Benchmark,
        context: str = "",
        model: str | None = None,
    ) -> tuple[bool, list[str], float]:
        """Visual shadow ray with structured alignment scoring.

        Returns (visible, occlusion_reasons, alignment_score).
        """
        imgs: list[ImageInput] = []
        for gi in board.images[:3]:
            imgs.append(ImageInput(data=gi.data, mime_type=gi.mime_type))
        if ref_images:
            imgs.extend(ref_images[:3])

        prompt = _SHADOW_PROMPT.format(
            context=context[:2000] if context else board.annotation[:2000],
            style_constraints=json.dumps(benchmark.style_anchors[:10]),
            exclusions_block=_exclusions_block(benchmark.style_exclusions),
            candidate=board.annotation[:3000],
        )
        prompt += (
            "\n\nCandidate mood board images and reference images are attached. "
            "Perform a thorough visual consistency audit. "
            "CRITICAL: Check images for FORBIDDEN elements first."
        )

        resp = await self._llm.generate(
            prompt, system=_SHADOW_SYSTEM,
            temperature=0.1, max_tokens=1024, model=model,
            images=imgs if imgs else None,
        )
        data = _parse_json(resp.content)
        alignment = float(data.get("alignment_score", 0.6))
        alignment = max(0.0, min(1.0, alignment))
        excl_violations = data.get("exclusion_violations", [])
        if excl_violations:
            alignment = min(alignment, EXCLUSION_PENALTY_CAP)
        visible = alignment >= 0.5 and data.get("visible", True)
        reasons = data.get("occlusion_reasons", [])
        return bool(visible), list(reasons), alignment

    async def score_document(
        self,
        sections: list[str],
        benchmark: Benchmark,
        model: str | None = None,
    ) -> MultiDimScore:
        joined = "\n\n".join(
            f"## Section {i + 1}\n{s}" for i, s in enumerate(sections)
        )
        from .benchmark import StepDefinition

        full_criteria = StepCriteria(
            step=StepDefinition(index=0, title="Full Document"),
            dimensions=benchmark.dimensions,
            style_constraints=benchmark.style_anchors,
        )
        return await self.score_candidate(
            joined, full_criteria, context="Full document evaluation", model=model,
        )


# ---------------------------------------------------------------------------
# Ensemble scorer — multi-LLM cross-validation
# ---------------------------------------------------------------------------


class EnsembleScorer:
    """Aggregates scores from multiple LLM judges.

    Strategy: each LLM independently scores the candidate.  The final
    per-dimension score is the *trimmed low mean* — drop the highest score,
    average the rest.  If any single LLM gives a dimension score below the
    ``veto_threshold``, that dimension is capped at the veto value.
    """

    def __init__(
        self,
        llms: list[LLMAdapter],
        *,
        adversarial: bool = True,
        veto_threshold: float = 0.3,
    ) -> None:
        if not llms:
            raise ValueError("EnsembleScorer requires at least one LLMAdapter")
        self._scorers = [Scorer(llm, adversarial=adversarial) for llm in llms]
        self._veto_threshold = veto_threshold
        self._primary = self._scorers[0]

    @property
    def primary_scorer(self) -> Scorer:
        return self._primary

    @staticmethod
    def _trimmed_low_mean(values: list[float]) -> float:
        """Drop the highest value, average the rest."""
        if len(values) <= 1:
            return values[0] if values else 0.0
        s = sorted(values)
        trimmed = s[:-1]
        return sum(trimmed) / len(trimmed)

    def _ensemble_merge(
        self,
        all_results: list[MultiDimScore],
        dims: list[QualityDimension],
    ) -> MultiDimScore:
        if len(all_results) == 1:
            return all_results[0]

        dim_buckets: dict[str, list[DimensionScore]] = {}
        for result in all_results:
            for ds in result.dimension_scores:
                dim_buckets.setdefault(ds.dimension, []).append(ds)

        merged_dims: list[DimensionScore] = []
        for dim_name, entries in dim_buckets.items():
            scores = [e.score for e in entries]
            final_score = self._trimmed_low_mean(scores)

            if any(s < self._veto_threshold for s in scores):
                final_score = min(final_score, self._veto_threshold)

            worst = min(entries, key=lambda e: e.score)
            merged_dims.append(DimensionScore(
                dimension=dim_name,
                score=round(final_score, 4),
                reasoning=worst.reasoning,
                suggestion=worst.suggestion,
            ))

        agg = _weighted_aggregate(merged_dims, dims)
        shadow_visible = all(r.shadow_visible for r in all_results)
        alignment = min(r.shadow_alignment for r in all_results)
        occlusion = []
        seen: set[str] = set()
        for r in all_results:
            for reason in r.occlusion_reasons:
                if reason not in seen:
                    occlusion.append(reason)
                    seen.add(reason)

        excl_violations: list[str] = []
        excl_seen: set[str] = set()
        for r in all_results:
            for v in r.exclusion_violations:
                if v not in excl_seen:
                    excl_violations.append(v)
                    excl_seen.add(v)
        if excl_violations:
            agg = min(agg, EXCLUSION_PENALTY_CAP)

        return MultiDimScore(
            dimension_scores=merged_dims,
            aggregate=agg,
            shadow_visible=shadow_visible,
            shadow_alignment=alignment,
            occlusion_reasons=occlusion,
            exclusion_violations=excl_violations,
        )

    async def score_mood_board(
        self,
        board: MoodBoard,
        criteria: StepCriteria,
        context: str = "",
        prior_boards: list[MoodBoard] | None = None,
        model: str | None = None,
    ) -> MultiDimScore:
        tasks = [
            scorer.score_mood_board(board, criteria, context, prior_boards, model)
            for scorer in self._scorers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid: list[MultiDimScore] = [
            r for r in results if isinstance(r, MultiDimScore)
        ]
        if not valid:
            logger.error("All ensemble scorers failed, using fallback")
            return MultiDimScore(
                dimension_scores=[
                    DimensionScore(
                        dimension=d.name, score=0.3,
                        reasoning="All scorers failed",
                    )
                    for d in criteria.dimensions
                ],
                aggregate=0.3,
            )

        return self._ensemble_merge(valid, criteria.dimensions)

    async def shadow_ray_visual(
        self,
        board: MoodBoard,
        ref_images: list[ImageInput] | None,
        benchmark: Benchmark,
        context: str = "",
        model: str | None = None,
    ) -> tuple[bool, list[str], float]:
        """Run shadow ray across all judges; any veto -> not visible."""
        tasks = [
            scorer.shadow_ray_visual(board, ref_images, benchmark, context, model)
            for scorer in self._scorers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_reasons: list[str] = []
        min_alignment = 1.0
        any_visible = False
        valid_count = 0
        seen: set[str] = set()

        for r in results:
            if isinstance(r, Exception):
                logger.warning("Shadow ray scorer failed: %s", r)
                continue
            visible, reasons, alignment = r
            valid_count += 1
            min_alignment = min(min_alignment, alignment)
            if visible:
                any_visible = True
            for reason in reasons:
                if reason not in seen:
                    all_reasons.append(reason)
                    seen.add(reason)

        if valid_count == 0:
            return False, ["All shadow ray scorers failed"], 0.0

        final_visible = min_alignment >= 0.5 and any_visible
        return final_visible, all_reasons, min_alignment

    async def score_document(
        self,
        sections: list[str],
        benchmark: Benchmark,
        model: str | None = None,
    ) -> MultiDimScore:
        """Ensemble-aggregated document scoring for MLT."""
        tasks = [
            scorer.score_document(sections, benchmark, model=model)
            for scorer in self._scorers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        valid: list[MultiDimScore] = [
            r for r in results if isinstance(r, MultiDimScore)
        ]
        if not valid:
            logger.error("All ensemble scorers failed on score_document")
            return MultiDimScore(
                dimension_scores=[
                    DimensionScore(
                        dimension=d.name, score=0.3,
                        reasoning="All scorers failed",
                    )
                    for d in benchmark.dimensions
                ],
                aggregate=0.3,
            )

        return self._ensemble_merge(valid, benchmark.dimensions)
