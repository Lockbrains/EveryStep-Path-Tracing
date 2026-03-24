"""Structured feedback extraction and prompt injection.

Converts multi-dimensional scorer output into actionable constraints for
the next sampling step — this is the importance sampling direction guide.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .benchmark import Benchmark, StepCriteria, StepDefinition
from .scorer import MultiDimScore


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class StructuredFeedback(BaseModel):
    """Feedback extracted from scorer output for the next step."""

    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    hard_constraints: list[str] = Field(default_factory=list)
    soft_guidance: list[str] = Field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.strengths and not self.weaknesses


# ---------------------------------------------------------------------------
# Feedback extractor
# ---------------------------------------------------------------------------

_WEAKNESS_THRESHOLD = 0.5
_STRENGTH_THRESHOLD = 0.75
_MAX_WEAKNESSES = 3


class FeedbackExtractor:
    @staticmethod
    def extract(
        score: MultiDimScore,
        criteria: StepCriteria | None = None,
    ) -> StructuredFeedback:
        strengths: list[str] = []
        weaknesses: list[str] = []
        hard_constraints: list[str] = []
        soft_guidance: list[str] = []

        for ds in score.dimension_scores:
            if ds.score >= _STRENGTH_THRESHOLD:
                strengths.append(f"[{ds.dimension}] {ds.reasoning}")
            elif ds.score < _WEAKNESS_THRESHOLD:
                weaknesses.append(f"[{ds.dimension}] {ds.reasoning}")
                if ds.suggestion:
                    soft_guidance.append(ds.suggestion)

        weaknesses = weaknesses[:_MAX_WEAKNESSES]
        soft_guidance = soft_guidance[:_MAX_WEAKNESSES]

        if score.exclusion_violations:
            for v in score.exclusion_violations:
                hard_constraints.append(f"FORBIDDEN: {v}")

        if not score.shadow_visible and score.occlusion_reasons:
            for reason in score.occlusion_reasons[:2]:
                soft_guidance.append(f"Consistency note: {reason}")

        return StructuredFeedback(
            strengths=strengths,
            weaknesses=weaknesses,
            hard_constraints=hard_constraints,
            soft_guidance=soft_guidance,
        )


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------


class PromptBuilder:
    @staticmethod
    def build(
        step: StepDefinition,
        brief: str,
        prior_sections: list[str],
        feedback: StructuredFeedback | None,
        benchmark: Benchmark,
        criteria: StepCriteria | None = None,
    ) -> str:
        parts: list[str] = []

        if benchmark.style_exclusions:
            excl = "\n".join(f"- {e}" for e in benchmark.style_exclusions)
            parts.append(
                f"!! ABSOLUTELY FORBIDDEN — these must NEVER appear:\n{excl}\n"
            )

        parts.append(f"# Task: {step.title}\n")
        parts.append(f"Creative brief:\n{brief}\n")

        if prior_sections:
            prior = "\n\n---\n\n".join(
                f"[Section {i + 1}]\n{s[:1500]}" for i, s in enumerate(prior_sections)
            )
            parts.append(f"Prior completed sections (maintain consistency):\n{prior}\n")

        if benchmark.style_anchors:
            anchors = "\n".join(f"- {a}" for a in benchmark.style_anchors[:8])
            parts.append(f"Style requirements:\n{anchors}\n")

        if criteria and criteria.structural_template:
            parts.append(
                f"Expected structure for this section:\n{criteria.structural_template}\n"
            )

        if feedback and not feedback.is_empty():
            if feedback.hard_constraints:
                hc = "\n".join(f"- {c}" for c in feedback.hard_constraints)
                parts.append(f"HARD CONSTRAINTS (must follow):\n{hc}\n")

            if feedback.weaknesses:
                wk = "\n".join(f"- {w}" for w in feedback.weaknesses[:5])
                parts.append(
                    f"Previous weaknesses to address in this section:\n{wk}\n"
                )

            if feedback.soft_guidance:
                sg = "\n".join(f"- {g}" for g in feedback.soft_guidance[:5])
                parts.append(f"Improvement guidance:\n{sg}\n")

            if feedback.strengths:
                st = "\n".join(f"- {s}" for s in feedback.strengths[:3])
                parts.append(f"Strengths to maintain:\n{st}\n")

        if criteria:
            dim_names = [d.name for d in criteria.dimensions[:6]]
            parts.append(
                f"You will be evaluated on: {', '.join(dim_names)}.\n"
                f"Focus especially on dimensions where prior sections scored low.\n"
            )

        parts.append(
            f"Write the '{step.title}' section now. Be specific and actionable."
        )

        return "\n".join(parts)

    @staticmethod
    def build_system(benchmark: Benchmark) -> str:
        """Build system prompt from benchmark context."""
        parts = ["You are an expert creative specification writer."]
        if benchmark.style_anchors:
            parts.append(
                "Adhere strictly to these style anchors: "
                + "; ".join(benchmark.style_anchors[:5])
                + "."
            )
        if benchmark.structural_patterns:
            parts.append(
                "Follow these structural patterns: "
                + "; ".join(benchmark.structural_patterns[:3])
                + "."
            )
        return " ".join(parts)
