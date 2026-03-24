"""Russian Roulette with strict path termination and retry.

Probabilistically terminates low-quality paths to save computation.
When terminated, produces retry feedback so the step can be re-sampled
with adjusted constraints. Surviving paths receive weight compensation
(1/q) to maintain unbiasedness.

Key design choices (vs. the original lenient version):
- Hard quality gate: aggregate below HARD_FLOOR -> unconditional termination.
- Progressive threshold: later steps face higher bars (consistency matters more).
- Shadow alignment is continuous, not binary. Low alignment severely penalises
  survival probability instead of a mild 0.5 multiplier.
"""

from __future__ import annotations

import random

from pydantic import BaseModel, Field

from .feedback import FeedbackExtractor, StructuredFeedback
from .scorer import MultiDimScore
from .benchmark import StepCriteria

HARD_FLOOR = 0.25
PROGRESSIVE_INCREMENT = 0.02
SHADOW_ALIGNMENT_WEIGHT = 0.7


class RRResult(BaseModel):
    continue_path: bool
    weight: float = Field(ge=0.0, default=1.0)
    survival_probability: float = Field(ge=0.0, le=1.0, default=1.0)
    retry_feedback: StructuredFeedback | None = None


class RussianRoulette:
    def __init__(self, max_retries: int = 3) -> None:
        self.max_retries = max_retries

    def decide(
        self,
        score: MultiDimScore,
        threshold: float,
        criteria: StepCriteria | None = None,
        shadow_visible: bool = True,
        step_index: int = 0,
    ) -> RRResult:
        """Apply Russian Roulette with strict quality gating.

        ``threshold`` is the *base* survival bar (recommended default: 0.7
        with calibrated scoring).  It is automatically raised for later steps
        via ``step_index * PROGRESSIVE_INCREMENT``.

        Hard floor: any aggregate < HARD_FLOOR is unconditionally terminated
        regardless of threshold.

        Shadow alignment (0-1 continuous) replaces the old binary penalty.
        When ``shadow_visible`` is False and alignment info is available on
        ``score.shadow_alignment``, survival probability is heavily penalised.
        """
        if threshold <= 0:
            return RRResult(continue_path=True, weight=1.0, survival_probability=1.0)

        agg = score.aggregate

        if agg < HARD_FLOOR:
            fb = FeedbackExtractor.extract(score, criteria)
            return RRResult(
                continue_path=False,
                weight=0.0,
                survival_probability=0.0,
                retry_feedback=fb,
            )

        effective_threshold = threshold + step_index * PROGRESSIVE_INCREMENT

        q = min(agg / effective_threshold, 1.0)

        shadow_align = getattr(score, "shadow_alignment", 1.0)
        if not shadow_visible:
            q *= shadow_align * SHADOW_ALIGNMENT_WEIGHT
        elif shadow_align < 1.0:
            q *= (0.5 + 0.5 * shadow_align)

        weakest = score.weakest_dimensions(2)
        if weakest and weakest[0].score < 0.25:
            q *= 0.5

        q = max(0.0, min(1.0, q))

        if q <= 0:
            fb = FeedbackExtractor.extract(score, criteria)
            return RRResult(
                continue_path=False,
                weight=0.0,
                survival_probability=0.0,
                retry_feedback=fb,
            )

        if random.random() < q:
            return RRResult(
                continue_path=True,
                weight=1.0 / q,
                survival_probability=q,
            )

        fb = FeedbackExtractor.extract(score, criteria)
        return RRResult(
            continue_path=False,
            weight=0.0,
            survival_probability=q,
            retry_feedback=fb,
        )
