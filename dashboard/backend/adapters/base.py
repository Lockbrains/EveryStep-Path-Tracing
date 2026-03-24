from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ImageInput(BaseModel):
    """Base64-encoded image for vision models."""

    data: str
    mime_type: str = "image/png"


class ImageOutput(BaseModel):
    """A generated image returned by a multimodal model."""

    data: str  # base64
    mime_type: str = "image/png"


class LLMResponse(BaseModel):
    content: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0


class MultimodalResponse(BaseModel):
    """Response that may contain both text and generated images."""

    text: str = ""
    images: list[ImageOutput] = Field(default_factory=list)
    model: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    cost: float = 0.0
    latency_ms: float = 0.0


class LLMAdapter(ABC):
    default_model: str = ""

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        model: str | None = None,
        images: list[ImageInput] | None = None,
    ) -> LLMResponse:
        pass

    async def generate_multimodal(
        self,
        prompt: str,
        system: str | None = None,
        temperature: float = 0.8,
        max_tokens: int = 4096,
        model: str | None = None,
        images: list[ImageInput] | None = None,
    ) -> MultimodalResponse:
        """Generate response with both text and images.

        Default implementation falls back to text-only generation.
        Override in adapters that support native image generation.
        """
        resp = await self.generate(
            prompt, system=system, temperature=temperature,
            max_tokens=max_tokens, model=model, images=images,
        )
        return MultimodalResponse(
            text=resp.content, images=[], model=resp.model,
            tokens_in=resp.tokens_in, tokens_out=resp.tokens_out,
            cost=resp.cost, latency_ms=resp.latency_ms,
        )

    @abstractmethod
    def get_cost(self, tokens_in: int, tokens_out: int) -> float:
        pass

    def _warn_disabled(self, name: str) -> None:
        logger.warning("%s adapter disabled: missing API key or client", name)
