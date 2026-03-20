from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class LLMResponse(BaseModel):
    content: str
    model: str
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
    ) -> LLMResponse:
        pass

    @abstractmethod
    def get_cost(self, tokens_in: int, tokens_out: int) -> float:
        pass

    def _warn_disabled(self, name: str) -> None:
        logger.warning("%s adapter disabled: missing API key or client", name)
