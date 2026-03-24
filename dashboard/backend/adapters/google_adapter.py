from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import time

import google.generativeai as genai

from .base import ImageInput, ImageOutput, LLMAdapter, LLMResponse, MultimodalResponse

logger = logging.getLogger(__name__)

GEMINI_FLASH_INPUT_PER_1M = 0.10
GEMINI_FLASH_OUTPUT_PER_1M = 0.40

IMAGE_GEN_MODEL = "gemini-3-pro-image-preview"


class GoogleAdapter(LLMAdapter):
    default_model = "gemini-3-flash-preview"

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("GOOGLE_API_KEY")
        self._enabled = bool(key)
        if key:
            genai.configure(api_key=key)
        else:
            self._warn_disabled("Google Generative AI")

    def get_cost(self, tokens_in: int, tokens_out: int) -> float:
        return (
            (tokens_in / 1_000_000) * GEMINI_FLASH_INPUT_PER_1M
            + (tokens_out / 1_000_000) * GEMINI_FLASH_OUTPUT_PER_1M
        )

    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
        images: list[ImageInput] | None = None,
    ) -> LLMResponse:
        m = model or self.default_model
        if not self._enabled:
            return LLMResponse(
                content=f"[google-mock] {prompt[:200]}…",
                model=m,
                tokens_in=len(prompt) // 4,
                tokens_out=64,
                cost=0.0,
                latency_ms=0.0,
            )
        t0 = time.perf_counter()

        def _call() -> tuple[str, int, int]:
            model_obj = genai.GenerativeModel(
                m,
                system_instruction=system or None,
            )
            parts: list = [prompt]
            if images:
                try:
                    from PIL import Image

                    for img in images:
                        raw = base64.b64decode(img.data)
                        pil_img = Image.open(io.BytesIO(raw))
                        parts.append(pil_img)
                except ImportError:
                    for img in images:
                        parts.append({
                            "mime_type": img.mime_type,
                            "data": base64.b64decode(img.data),
                        })

            gen = model_obj.generate_content(
                parts,
                generation_config=genai.types.GenerationConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                ),
            )
            text = gen.text or ""
            meta = getattr(gen, "usage_metadata", None)
            tin = getattr(meta, "prompt_token_count", None) or (len(prompt) // 4)
            tout = getattr(meta, "candidates_token_count", None) or (len(text) // 4)
            return text, int(tin), int(tout)

        content, tokens_in, tokens_out = await asyncio.to_thread(_call)
        latency_ms = (time.perf_counter() - t0) * 1000
        return LLMResponse(
            content=content,
            model=m,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=self.get_cost(tokens_in, tokens_out),
            latency_ms=latency_ms,
        )

    async def generate_multimodal(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 4096,
        model: str | None = None,
        images: list[ImageInput] | None = None,
    ) -> MultimodalResponse:
        m = model or IMAGE_GEN_MODEL
        if not self._enabled:
            return MultimodalResponse(
                text=f"[google-mock-multimodal] {prompt[:200]}…",
                images=[], model=m,
                tokens_in=len(prompt) // 4, tokens_out=64,
                cost=0.0, latency_ms=0.0,
            )
        t0 = time.perf_counter()

        def _call() -> tuple[str, list[ImageOutput], int, int]:
            model_obj = genai.GenerativeModel(
                m,
                system_instruction=system or None,
            )
            parts: list = [prompt]
            if images:
                try:
                    from PIL import Image

                    for img in images:
                        raw = base64.b64decode(img.data)
                        pil_img = Image.open(io.BytesIO(raw))
                        parts.append(pil_img)
                except ImportError:
                    for img in images:
                        parts.append({
                            "mime_type": img.mime_type,
                            "data": base64.b64decode(img.data),
                        })

            gen = model_obj.generate_content(
                parts,
                generation_config={
                    "response_modalities": ["TEXT", "IMAGE"],
                    "temperature": temperature,
                    "max_output_tokens": max_tokens,
                },
            )

            text_parts: list[str] = []
            img_outputs: list[ImageOutput] = []

            for part in gen.parts:
                if hasattr(part, "text") and part.text:
                    text_parts.append(part.text)
                elif hasattr(part, "inline_data") and part.inline_data:
                    blob = part.inline_data
                    mime = getattr(blob, "mime_type", "image/png")
                    raw_bytes = blob.data
                    if isinstance(raw_bytes, bytes):
                        b64 = base64.b64encode(raw_bytes).decode()
                    else:
                        b64 = str(raw_bytes)
                    img_outputs.append(ImageOutput(data=b64, mime_type=mime))

            text = "\n".join(text_parts)
            meta = getattr(gen, "usage_metadata", None)
            tin = getattr(meta, "prompt_token_count", None) or (len(prompt) // 4)
            tout = getattr(meta, "candidates_token_count", None) or (len(text) // 4 + len(img_outputs) * 258)
            return text, img_outputs, int(tin), int(tout)

        text, img_outputs, tokens_in, tokens_out = await asyncio.to_thread(_call)
        latency_ms = (time.perf_counter() - t0) * 1000
        return MultimodalResponse(
            text=text,
            images=img_outputs,
            model=m,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=self.get_cost(tokens_in, tokens_out),
            latency_ms=latency_ms,
        )
