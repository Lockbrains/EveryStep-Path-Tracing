from __future__ import annotations

import os
import time

from anthropic import AsyncAnthropic

from .base import LLMAdapter, LLMResponse

HAIKU_INPUT_PER_1M = 0.80
HAIKU_OUTPUT_PER_1M = 4.00


class AnthropicAdapter(LLMAdapter):
    default_model = "claude-3-5-haiku-20241022"

    def __init__(self, api_key: str | None = None) -> None:
        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        self._client: AsyncAnthropic | None = None
        if key:
            self._client = AsyncAnthropic(api_key=key)
        else:
            self._warn_disabled("Anthropic")

    def get_cost(self, tokens_in: int, tokens_out: int) -> float:
        return (
            (tokens_in / 1_000_000) * HAIKU_INPUT_PER_1M
            + (tokens_out / 1_000_000) * HAIKU_OUTPUT_PER_1M
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
                content=f"[anthropic-mock] {prompt[:200]}…",
                model=m,
                tokens_in=len(prompt) // 4,
                tokens_out=64,
                cost=0.0,
                latency_ms=0.0,
            )
        t0 = time.perf_counter()
        msg = await self._client.messages.create(
            model=m,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system or "",
            messages=[{"role": "user", "content": prompt}],
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        block = msg.content[0]
        content = block.text if hasattr(block, "text") else str(block)
        tokens_in = msg.usage.input_tokens
        tokens_out = msg.usage.output_tokens
        return LLMResponse(
            content=content,
            model=m,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost=self.get_cost(tokens_in, tokens_out),
            latency_ms=latency_ms,
        )
