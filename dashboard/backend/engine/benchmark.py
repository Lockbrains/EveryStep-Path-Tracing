"""Backward path: analyze references to derive evaluation dimensions.

Analogous to eye-tracing in bidirectional path tracing — we start from
known-good outputs and work backwards to derive what makes them good.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import BaseModel, Field

from adapters.base import ImageInput, LLMAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


class QualityDimension(BaseModel):
    """A single evaluation axis extracted from reference analysis."""

    name: str
    description: str
    weight: float = Field(ge=0.0, le=1.0, default=0.5)
    rubric_low: str = ""
    rubric_high: str = ""


class Benchmark(BaseModel):
    """Complete benchmark derived from backward-path reference analysis."""

    dimensions: list[QualityDimension] = Field(default_factory=list)
    style_anchors: list[str] = Field(default_factory=list)
    style_exclusions: list[str] = Field(default_factory=list)
    structural_patterns: list[str] = Field(default_factory=list)
    reference_summaries: list[str] = Field(default_factory=list)


class StepDefinition(BaseModel):
    """Describes one step in a multi-step pipeline."""

    index: int
    title: str
    description: str = ""


class StepCriteria(BaseModel):
    """Step-specific evaluation criteria derived from the global benchmark."""

    step: StepDefinition
    dimensions: list[QualityDimension] = Field(default_factory=list)
    style_constraints: list[str] = Field(default_factory=list)
    style_exclusions: list[str] = Field(default_factory=list)
    structural_template: str | None = None


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_ANALYZE_SYSTEM = (
    "You are an expert creative-quality analyst. "
    "Given reference materials and a task description, you extract "
    "structured quality dimensions, style anchors, and structural patterns. "
    "Always respond with valid JSON only — no markdown fences, no commentary."
)

_ANALYZE_PROMPT = """\
Task description:
{task_desc}

Reference materials:
{references}

Analyze these references and extract:

1. "dimensions": a list of 5-8 quality dimensions that distinguish good output \
from bad. Each dimension has:
   - "name": short label (e.g. "visual_coherence")
   - "description": what this dimension measures
   - "weight": relative importance 0.0-1.0
   - "rubric_low": what a score near 0 looks like
   - "rubric_high": what a score near 1 looks like

2. "style_anchors": 5-10 specific style descriptors extracted from the \
references (tone, vocabulary register, visual language, etc.)

3. "style_exclusions": THIS IS THE MOST IMPORTANT SECTION. List 5-10 specific \
visual elements, techniques, or rendering styles that are ABSENT from ALL \
references and must NEVER appear in generated output. \
Negative constraints ("what must NOT be there") carry MORE weight than positive \
style descriptors ("what should be there"). \
Analyze the references CAREFULLY for what they do NOT have:
   - Outline/stroke treatment: Are objects drawn with visible outlines/edges, or \
are they rendered without outlines? (e.g. "no visible outlines or edge strokes")
   - Rendering technique: What rendering approaches are NOT used? \
(e.g. "no cel-shading", "no photorealistic rendering")
   - Color treatment: What color methods are avoided? \
(e.g. "no monochrome palettes", "no neon/fluorescent colors")
   - Texture approach: What texturing methods are absent? \
(e.g. "no realistic material textures", "no noise/grain overlays")
   - Effects: What visual effects are not present? \
(e.g. "no drop shadows", "no lens flare", "no motion blur")
   - Other: Any other visual element that is conspicuously absent from the references.

4. "structural_patterns": 3-5 patterns describing how sections are organized \
in the references (e.g. "each section opens with a one-line summary")

5. "reference_summaries": a concise 2-3 sentence summary of each reference

Respond with a single JSON object matching this schema exactly."""

_STEP_CRITERIA_SYSTEM = (
    "You are a quality-criteria specialist. Given a global benchmark and a "
    "specific pipeline step, derive step-specific evaluation criteria. "
    "Respond with valid JSON only."
)

_STEP_CRITERIA_PROMPT = """\
Global benchmark dimensions:
{dimensions_json}

Global style anchors:
{style_json}

Global style EXCLUSIONS (FORBIDDEN elements — these must NEVER appear):
{exclusions_json}

Global structural patterns:
{structure_json}

Pipeline step:
  title: {step_title}
  description: {step_desc}
  index: {step_index} (of {total_steps} total)

Derive step-specific criteria:

1. "dimensions": select and re-weight the global dimensions for THIS step. \
Adjust weights so they sum to roughly 1.0. Add step-specific rubric details \
if needed.

2. "style_constraints": 3-5 style rules specific to this step, derived from \
the global style_anchors.

3. "style_exclusions": carry forward ALL global exclusions and add any \
step-specific exclusions. These FORBIDDEN elements must never appear.

4. "structural_template": a brief template or outline that this step's \
output should follow, based on the structural_patterns.

Respond with a single JSON object."""


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


def _parse_json_response(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from LLM output."""
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
    logger.warning("Failed to parse JSON from LLM response, using fallback")
    return {}


def _build_default_benchmark(task_desc: str) -> Benchmark:
    """Fallback benchmark when no references or LLM parse failure."""
    return Benchmark(
        dimensions=[
            QualityDimension(
                name="relevance",
                description="How relevant the output is to the task requirements",
                weight=0.25,
                rubric_low="Off-topic or ignores the brief",
                rubric_high="Directly addresses every aspect of the brief",
            ),
            QualityDimension(
                name="coherence",
                description="Internal logical consistency and flow",
                weight=0.2,
                rubric_low="Contradictory or disjointed",
                rubric_high="Every element supports a unified vision",
            ),
            QualityDimension(
                name="specificity",
                description="Level of concrete, actionable detail",
                weight=0.2,
                rubric_low="Vague generalities only",
                rubric_high="Precise specs, values, and examples",
            ),
            QualityDimension(
                name="creativity",
                description="Originality and creative value",
                weight=0.15,
                rubric_low="Generic, derivative",
                rubric_high="Distinctive and memorable",
            ),
            QualityDimension(
                name="consistency",
                description="Alignment with prior sections and overall style",
                weight=0.2,
                rubric_low="Clashes with established tone/content",
                rubric_high="Seamlessly extends the document",
            ),
        ],
        style_anchors=["professional creative specification"],
        structural_patterns=["structured sections with clear headings"],
        reference_summaries=[f"Task-derived baseline for: {task_desc[:200]}"],
    )


class BenchmarkAnalyzer:
    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    async def analyze_references(
        self,
        references: list[str],
        task_desc: str,
        model: str | None = None,
        images: list[ImageInput] | None = None,
    ) -> Benchmark:
        has_text = bool(references)
        has_images = bool(images)

        if not has_text and not has_images:
            return _build_default_benchmark(task_desc)

        refs_text = ""
        if references:
            refs_text = "\n\n---\n\n".join(
                f"[Reference {i + 1}]\n{r[:3000]}" for i, r in enumerate(references)
            )

        image_note = ""
        if has_images:
            image_note = (
                f"\n\n[{len(images)} reference image(s) are attached. "
                "Analyze their visual style, color palette, composition, "
                "mood, and any recurring design patterns.]"
            )

        prompt = _ANALYZE_PROMPT.format(
            task_desc=task_desc,
            references=(refs_text or "(no text references)") + image_note,
        )

        resp = await self._llm.generate(
            prompt,
            system=_ANALYZE_SYSTEM,
            temperature=0.3,
            max_tokens=4096,
            model=model,
            images=images,
        )
        data = _parse_json_response(resp.content)
        if not data.get("dimensions"):
            logger.warning("Reference analysis returned no dimensions, using fallback")
            return _build_default_benchmark(task_desc)

        dims = []
        for d in data.get("dimensions", []):
            try:
                dims.append(QualityDimension(**d))
            except Exception:
                continue

        return Benchmark(
            dimensions=dims or _build_default_benchmark(task_desc).dimensions,
            style_anchors=data.get("style_anchors", []),
            style_exclusions=data.get("style_exclusions", []),
            structural_patterns=data.get("structural_patterns", []),
            reference_summaries=data.get("reference_summaries", []),
        )

    async def derive_step_criteria(
        self,
        benchmark: Benchmark,
        step: StepDefinition,
        total_steps: int = 5,
        model: str | None = None,
    ) -> StepCriteria:
        dims_json = json.dumps(
            [d.model_dump() for d in benchmark.dimensions], indent=2
        )
        prompt = _STEP_CRITERIA_PROMPT.format(
            dimensions_json=dims_json,
            style_json=json.dumps(benchmark.style_anchors),
            exclusions_json=json.dumps(benchmark.style_exclusions),
            structure_json=json.dumps(benchmark.structural_patterns),
            step_title=step.title,
            step_desc=step.description or step.title,
            step_index=step.index + 1,
            total_steps=total_steps,
        )
        resp = await self._llm.generate(
            prompt,
            system=_STEP_CRITERIA_SYSTEM,
            temperature=0.3,
            max_tokens=2048,
            model=model,
        )
        data = _parse_json_response(resp.content)

        step_dims = []
        for d in data.get("dimensions", []):
            try:
                step_dims.append(QualityDimension(**d))
            except Exception:
                continue
        if not step_dims:
            step_dims = list(benchmark.dimensions)

        raw_template = data.get("structural_template")
        if isinstance(raw_template, dict):
            import json as _json
            raw_template = _json.dumps(raw_template, indent=2)
        elif raw_template is not None and not isinstance(raw_template, str):
            raw_template = str(raw_template)

        raw_style = data.get("style_constraints", benchmark.style_anchors)
        if isinstance(raw_style, str):
            raw_style = [raw_style]
        elif not isinstance(raw_style, list):
            raw_style = list(benchmark.style_anchors)

        raw_exclusions = data.get("style_exclusions", benchmark.style_exclusions)
        if isinstance(raw_exclusions, str):
            raw_exclusions = [raw_exclusions]
        elif not isinstance(raw_exclusions, list):
            raw_exclusions = list(benchmark.style_exclusions)
        if not raw_exclusions:
            raw_exclusions = list(benchmark.style_exclusions)

        has_relevance = any(
            d.name == "step_relevance" for d in step_dims
        )
        if not has_relevance:
            step_dims.append(QualityDimension(
                name="step_relevance",
                description=(
                    f"How directly the candidate addresses the specific topic "
                    f"of THIS step: '{step.title}'. The output must focus on "
                    f"'{step.description or step.title}', not just match "
                    f"overall style."
                ),
                weight=0.25,
                rubric_low=(
                    "Ignores the step topic entirely; could belong to any step"
                ),
                rubric_high=(
                    f"Directly and specifically addresses '{step.title}' with "
                    f"dedicated content"
                ),
            ))

        return StepCriteria(
            step=step,
            dimensions=step_dims,
            style_constraints=raw_style,
            style_exclusions=raw_exclusions,
            structural_template=raw_template,
        )
