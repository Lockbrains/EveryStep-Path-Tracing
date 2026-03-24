"""MoodBoard generator with genuine Multi-Strategy sampling.

Each candidate is a set of generated images (3-4) plus a brief annotation,
created by calling a multimodal LLM that can output both text and images.

MIS channels are *truly* different distributions — separate temperatures,
system prompts, and context injection.  This ensures diverse candidates
rather than near-identical outputs from the same prompt.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Callable

from adapters.base import ImageInput, ImageOutput, LLMAdapter, MultimodalResponse
from .benchmark import Benchmark, StepDefinition
from .feedback import StructuredFeedback
from .mood_board import GeneratedImage, MoodBoard

logger = logging.getLogger(__name__)

ImageStoreFn = Callable[[str, str, str], str]

TARGET_IMAGES_PER_BOARD = 4
MAX_FILL_CALLS = 3


# ---------------------------------------------------------------------------
# MIS channel definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class MISChannel:
    name: str
    system_prompt: str
    temperature: float
    include_feedback: bool
    include_benchmark_anchors: bool
    extra_instruction: str = ""


CHANNEL_FREE = MISChannel(
    name="free",
    system_prompt=(
        "You are a creative visual art director. Explore fresh interpretations "
        "of the brief — try different angles, compositions, and moods while "
        "staying grounded in the reference material's visual language."
    ),
    temperature=0.9,
    include_feedback=False,
    include_benchmark_anchors=True,
    extra_instruction=(
        "Offer a fresh creative take, but stay within the established style. "
        "Do NOT introduce elements that are absent from the references."
    ),
)

CHANNEL_ANCHORED = MISChannel(
    name="anchored",
    system_prompt=(
        "You are a precise visual art director who prioritizes consistency "
        "and faithfulness to reference materials. Every image must closely "
        "match the established visual language — same color temperature, "
        "similar rendering style, coherent spatial logic."
    ),
    temperature=0.6,
    include_feedback=False,
    include_benchmark_anchors=True,
    extra_instruction=(
        "Stay close to the references. Match the established visual language exactly. "
        "Consistency is more important than novelty."
    ),
)

CHANNEL_GUIDED = MISChannel(
    name="guided",
    system_prompt=(
        "You are a corrective visual art director. You have received specific "
        "feedback about weaknesses in prior output. Your primary goal is to "
        "fix every identified issue while preserving existing strengths. "
        "Be methodical and address each weakness explicitly."
    ),
    temperature=0.75,
    include_feedback=True,
    include_benchmark_anchors=True,
    extra_instruction=(
        "Address EVERY weakness listed below. Do not ignore any constraint."
    ),
)


# ---------------------------------------------------------------------------
# Prompt builders per channel
# ---------------------------------------------------------------------------

def _forbidden_block(exclusions: list[str]) -> str:
    if not exclusions:
        return ""
    items = "\n".join(f"  - {e}" for e in exclusions)
    return (
        "!! ABSOLUTELY FORBIDDEN — these elements must NEVER appear "
        "in ANY generated image. Any image containing these will be "
        "immediately rejected:\n"
        f"{items}\n"
    )


def _build_base_prompt(
    step: StepDefinition,
    brief: str,
    prior_boards: list[MoodBoard],
    benchmark: Benchmark | None = None,
) -> str:
    parts: list[str] = []

    if benchmark and benchmark.style_exclusions:
        parts.append(_forbidden_block(benchmark.style_exclusions))

    parts.extend([
        f"Generate a mood board for: **{step.title}**\n"
        f"({step.description})\n",
        f"Creative brief: {brief}\n",
    ])

    if benchmark and benchmark.style_anchors:
        parts.append(
            "STYLE ANCHORS (follow closely):\n"
            + "\n".join(f"- {a}" for a in benchmark.style_anchors[:8])
        )

    if prior_boards:
        parts.append(
            f"\n{len(prior_boards)} previous step(s) have been completed. "
            "Their mood board images are attached.\n"
        )
    parts.append(
        "\nGenerate 3-4 images that form a cohesive mood board for this section. "
        "Also write a brief annotation (2-3 sentences) describing the visual direction."
    )
    return "\n".join(parts)


def _build_channel_prompt(
    channel: MISChannel,
    step: StepDefinition,
    brief: str,
    prior_boards: list[MoodBoard],
    feedback: StructuredFeedback | None,
    benchmark: Benchmark,
) -> str:
    parts: list[str] = []

    if benchmark.style_exclusions:
        parts.append(_forbidden_block(benchmark.style_exclusions))

    parts.extend([
        f"Generate a mood board for: **{step.title}**\n"
        f"({step.description})\n",
        f"Creative brief: {brief}\n",
    ])

    if channel.include_benchmark_anchors and benchmark.style_anchors:
        parts.append(
            "STYLE ANCHORS (follow closely):\n"
            + "\n".join(f"- {a}" for a in benchmark.style_anchors[:8])
        )
    if channel.include_benchmark_anchors and benchmark.structural_patterns:
        parts.append(
            "STRUCTURAL PATTERNS:\n"
            + "\n".join(f"- {p}" for p in benchmark.structural_patterns[:5])
        )

    if prior_boards:
        consistency_level = (
            "Match the established visual language exactly."
            if channel.name == "anchored"
            else "Maintain general visual consistency with prior steps."
        )
        parts.append(
            f"\n{len(prior_boards)} previous step(s) completed. "
            f"Their images are attached. {consistency_level}\n"
        )

    if channel.include_feedback and feedback and not feedback.is_empty():
        if feedback.hard_constraints:
            parts.append(
                "HARD CONSTRAINTS (MUST follow):\n"
                + "\n".join(f"- {c}" for c in feedback.hard_constraints)
            )
        if feedback.weaknesses:
            parts.append(
                "WEAKNESSES TO FIX (address each one):\n"
                + "\n".join(f"- {w}" for w in feedback.weaknesses)
            )
        if feedback.soft_guidance:
            parts.append(
                "Improvement guidance:\n"
                + "\n".join(f"- {g}" for g in feedback.soft_guidance[:5])
            )

    if channel.extra_instruction:
        parts.append(f"\n{channel.extra_instruction}")

    parts.append(
        "\nGenerate 3-4 images that form a cohesive mood board for this section. "
        "Also write a brief annotation (2-3 sentences) describing the visual direction."
    )
    return "\n".join(parts)


def _collect_prior_images(
    prior_boards: list[MoodBoard], max_images: int = 4,
) -> list[ImageInput]:
    inputs: list[ImageInput] = []
    for board in prior_boards:
        if board.images:
            img = board.images[0]
            inputs.append(ImageInput(data=img.data, mime_type=img.mime_type))
            if len(inputs) >= max_images:
                break
    return inputs


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class MoodBoardGenerator:
    def __init__(
        self,
        llm: LLMAdapter,
        image_store_fn: ImageStoreFn | None = None,
    ) -> None:
        self._llm = llm
        self._store_fn = image_store_fn

    def _store_image(self, output: ImageOutput) -> GeneratedImage:
        if self._store_fn:
            img_id = self._store_fn(
                output.data, output.mime_type, f"gen_{uuid.uuid4().hex[:8]}.png",
            )
        else:
            img_id = str(uuid.uuid4())
        return GeneratedImage(id=img_id, data=output.data, mime_type=output.mime_type)

    async def _fill_images(
        self,
        board: MoodBoard,
        step: StepDefinition,
        brief: str,
        benchmark: Benchmark | None,
        system: str,
        temperature: float,
        model: str | None,
        input_images: list[ImageInput] | None,
    ) -> MoodBoard:
        """Make additional calls if the board has fewer images than target."""
        remaining = TARGET_IMAGES_PER_BOARD - len(board.images)
        if remaining <= 0:
            return board

        fill_prompt_parts: list[str] = []
        if benchmark and benchmark.style_exclusions:
            fill_prompt_parts.append(_forbidden_block(benchmark.style_exclusions))
        fill_prompt_parts.append(
            f"Generate ONE image for the '{step.title}' section of an art bible.\n"
            f"({step.description})\n"
            f"Brief: {brief}\n"
        )
        if benchmark and benchmark.style_anchors:
            fill_prompt_parts.append(
                "STYLE ANCHORS:\n"
                + "\n".join(f"- {a}" for a in benchmark.style_anchors[:5])
            )
        if board.annotation:
            fill_prompt_parts.append(
                f"\nVisual direction already established:\n{board.annotation[:500]}\n"
                "Generate a NEW image that complements the existing mood board "
                "with a different angle, composition, or focus area."
            )
        fill_prompt = "\n".join(fill_prompt_parts)

        calls = min(remaining, MAX_FILL_CALLS)
        tasks = [
            self._llm.generate_multimodal(
                fill_prompt,
                system=system,
                temperature=temperature,
                max_tokens=4096,
                model=model,
                images=input_images if input_images else None,
            )
            for _ in range(calls)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                logger.warning("Fill image call failed: %s", r)
                continue
            for out in r.images:
                board.images.append(self._store_image(out))
                if len(board.images) >= TARGET_IMAGES_PER_BOARD:
                    return board
        return board

    async def generate_one(
        self,
        step: StepDefinition,
        brief: str,
        prior_boards: list[MoodBoard],
        feedback: StructuredFeedback | None,
        benchmark: Benchmark,
        ref_images: list[ImageInput] | None = None,
        variant: str = "",
        model: str | None = None,
        *,
        system: str | None = None,
        temperature: float = 0.85,
    ) -> MoodBoard:
        if system is None:
            system = (
                "You are a visual art director creating mood boards. "
                "Generate cohesive, high-quality images that work together."
            )

        if variant:
            prompt = _build_base_prompt(step, brief, prior_boards, benchmark)
            prompt += f"\n\nVariant focus: {variant}"
            if feedback and not feedback.is_empty():
                if feedback.hard_constraints:
                    prompt += "\nCONSTRAINTS:\n" + "\n".join(
                        f"- {c}" for c in feedback.hard_constraints
                    )
                if feedback.weaknesses:
                    prompt += "\nFix these weaknesses:\n" + "\n".join(
                        f"- {w}" for w in feedback.weaknesses[:4]
                    )
        else:
            prompt = _build_base_prompt(step, brief, prior_boards, benchmark)

        input_images = list(ref_images or [])
        input_images.extend(_collect_prior_images(prior_boards))

        resp: MultimodalResponse = await self._llm.generate_multimodal(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=4096,
            model=model,
            images=input_images if input_images else None,
        )

        gen_images = [self._store_image(out) for out in resp.images]
        annotation = resp.text.strip() if resp.text else f"Mood board for {step.title}"

        board = MoodBoard(
            images=gen_images,
            annotation=annotation,
            step_index=step.index,
        )
        return await self._fill_images(
            board, step, brief, benchmark, system, temperature,
            model, input_images if input_images else None,
        )

    async def _generate_channel(
        self,
        channel: MISChannel,
        step: StepDefinition,
        brief: str,
        prior_boards: list[MoodBoard],
        feedback: StructuredFeedback | None,
        benchmark: Benchmark,
        ref_images: list[ImageInput] | None = None,
        model: str | None = None,
    ) -> MoodBoard:
        prompt = _build_channel_prompt(
            channel, step, brief, prior_boards, feedback, benchmark,
        )
        input_images = list(ref_images or [])
        input_images.extend(_collect_prior_images(prior_boards))

        resp: MultimodalResponse = await self._llm.generate_multimodal(
            prompt,
            system=channel.system_prompt,
            temperature=channel.temperature,
            max_tokens=4096,
            model=model,
            images=input_images if input_images else None,
        )

        gen_images = [self._store_image(out) for out in resp.images]
        annotation = resp.text.strip() if resp.text else f"Mood board for {step.title}"

        board = MoodBoard(
            images=gen_images,
            annotation=annotation,
            step_index=step.index,
        )
        return await self._fill_images(
            board, step, brief, benchmark, channel.system_prompt,
            channel.temperature, model,
            input_images if input_images else None,
        )

    async def sample_candidates(
        self,
        n: int,
        step: StepDefinition,
        brief: str,
        prior_boards: list[MoodBoard],
        feedback: StructuredFeedback | None,
        benchmark: Benchmark,
        ref_images: list[ImageInput] | None = None,
        strategy: str = "naive",
        model: str | None = None,
    ) -> list[MoodBoard]:

        if strategy == "mis":
            return await self._sample_mis(
                n, step, brief, prior_boards, feedback,
                benchmark, ref_images, model,
            )
        elif strategy == "importance" and feedback and not feedback.is_empty():
            return await self._sample_importance(
                n, step, brief, prior_boards, feedback,
                benchmark, ref_images, model,
            )
        else:
            return await self._sample_naive(
                n, step, brief, prior_boards, feedback,
                benchmark, ref_images, model,
            )

    async def _sample_naive(
        self,
        n: int,
        step: StepDefinition,
        brief: str,
        prior_boards: list[MoodBoard],
        feedback: StructuredFeedback | None,
        benchmark: Benchmark,
        ref_images: list[ImageInput] | None,
        model: str | None,
    ) -> list[MoodBoard]:
        tasks = [
            self.generate_one(
                step, brief, prior_boards, feedback, benchmark,
                ref_images=ref_images, model=model,
            )
            for _ in range(n)
        ]
        return list(await asyncio.gather(*tasks))

    async def _sample_importance(
        self,
        n: int,
        step: StepDefinition,
        brief: str,
        prior_boards: list[MoodBoard],
        feedback: StructuredFeedback | None,
        benchmark: Benchmark,
        ref_images: list[ImageInput] | None,
        model: str | None,
    ) -> list[MoodBoard]:
        weak_dims = []
        if feedback:
            weak_dims = [
                w.split("]")[0].replace("[", "")
                for w in feedback.weaknesses[:3]
            ]

        variants: list[str] = [f"Emphasize: {wd}" for wd in weak_dims]
        while len(variants) < n:
            variants.append("")
        variants = variants[:n]

        tasks = [
            self.generate_one(
                step, brief, prior_boards, feedback, benchmark,
                ref_images=ref_images, variant=v, model=model,
                temperature=0.75,
            )
            for v in variants
        ]
        return list(await asyncio.gather(*tasks))

    async def _sample_mis(
        self,
        n: int,
        step: StepDefinition,
        brief: str,
        prior_boards: list[MoodBoard],
        feedback: StructuredFeedback | None,
        benchmark: Benchmark,
        ref_images: list[ImageInput] | None,
        model: str | None,
    ) -> list[MoodBoard]:
        """True MIS: each channel uses a genuinely different distribution."""
        channels = [CHANNEL_FREE, CHANNEL_ANCHORED, CHANNEL_GUIDED]

        tasks: list = []
        channel_assignments: list[MISChannel] = []
        for i in range(n):
            ch = channels[i % len(channels)]
            channel_assignments.append(ch)
            tasks.append(
                self._generate_channel(
                    ch, step, brief, prior_boards, feedback,
                    benchmark, ref_images, model,
                )
            )

        results = list(await asyncio.gather(*tasks))

        for board, ch in zip(results, channel_assignments):
            board.strategy = ch.name

        return results
