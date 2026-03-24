from __future__ import annotations

import os
import time

from openai import AsyncOpenAI

from .base import ImageInput, LLMAdapter, LLMResponse

GPT4O_MINI_INPUT_PER_1M = 0.15
GPT4O_MINI_OUTPUT_PER_1M = 0.60


class OpenAIAdapter(LLMAdapter):
    default_model = "gpt-4o-mini"

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client: AsyncOpenAI | None = None
        if key:
            self._client = AsyncOpenAI(api_key=key)
        else:
            self._warn_disabled("OpenAI")

    def get_cost(self, tokens_in: int, tokens_out: int) -> float:
        return (
            (tokens_in / 1_000_000) * GPT4O_MINI_INPUT_PER_1M
            + (tokens_out / 1_000_000) * GPT4O_MINI_OUTPUT_PER_1M
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
        if not self._client:
            return LLMResponse(
                content=f"[openai-mock] {prompt[:200]}…",
                model=m,
                tokens_in=len(prompt) // 4,
                tokens_out=64,
                cost=0.0,
                latency_ms=0.0,
            )
        t0 = time.perf_counter()

        user_content: list[dict] | str
        if images:
            parts: list[dict] = [{"type": "text", "text": prompt}]
            for img in images:
                parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{img.mime_type};base64,{img.data}",
                        "detail": "low",
                    },
                })
            user_content = parts
        else:
            user_content = prompt

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_content})

        resp = await self._client.chat.completions.create(
            model=m,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        choice = resp.choices[0]
        content = choice.message.content or ""
        u = resp.usage
        tokens_in = u.prompt_tokens if u else len(prompt) // 4
        tokens_out = u.completion_tokens if u else len(content) // 4
        cost = self.get_cost(tokens_in, tokens_out)
        return LLMResponse(
            content=content,
            model=m,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=cost,
            latency_ms=latency_ms,
        )
