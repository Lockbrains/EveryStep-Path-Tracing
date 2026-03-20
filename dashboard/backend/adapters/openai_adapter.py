from __future__ import annotations

import os
import time

from openai import AsyncOpenAI

from .base import LLMAdapter, LLMResponse

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
        kwargs: dict = {
            "model": m,
            "messages": (
                [{"role": "system", "content": system}] if system else []
            )
            + [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        resp = await self._client.chat.completions.create(**kwargs)
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
