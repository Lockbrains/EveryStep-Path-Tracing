from __future__ import annotations

import asyncio
import os
import time

import google.generativeai as genai

from .base import LLMAdapter, LLMResponse

GEMINI_FLASH_INPUT_PER_1M = 0.10
GEMINI_FLASH_OUTPUT_PER_1M = 0.40


class GoogleAdapter(LLMAdapter):
    default_model = "gemini-2.0-flash"

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
            gen = model_obj.generate_content(
                prompt,
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
