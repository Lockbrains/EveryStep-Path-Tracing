from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, Field

from adapters.base import LLMAdapter, LLMResponse


class SampleResult(BaseModel):
    content: str
    quality_score: float = Field(ge=0.0, le=1.0)
    cost: float = Field(ge=0.0)
    strategy: str
    metadata: dict = Field(default_factory=dict)


class SamplingConfig(BaseModel):
    temperature: float = 0.8
    max_tokens: int = 2048
    seed: int | None = None


class MISWeights(BaseModel):
    weights: dict[str, float] = Field(default_factory=dict)
    balance_terms: dict[str, float] = Field(default_factory=dict)


StrategyName = Literal["free", "rag", "tool"]


class MonteCarloSampler:
    def __init__(self, llm: LLMAdapter) -> None:
        self._llm = llm

    async def _gen(
        self,
        task: str,
        model: str | None,
        config: SamplingConfig,
        system: str | None = None,
    ) -> LLMResponse:
        return await self._llm.generate(
            task,
            system=system,
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            model=model,
        )

    def _heuristic_quality(self, content: str, task: str) -> float:
        h = int(hashlib.sha256((content + task).encode()).hexdigest()[:8], 16)
        base = (h % 1000) / 1000.0
        length_bonus = min(len(content) / 2000.0, 0.2)
        return float(max(0.0, min(1.0, 0.3 + 0.5 * base + length_bonus)))

    async def naive_sample(
        self,
        task: str,
        n: int,
        model: str | None,
        config: SamplingConfig | None = None,
    ) -> list[SampleResult]:
        cfg = config or SamplingConfig()
        out: list[SampleResult] = []
        for _ in range(n):
            resp = await self._gen(task, model, cfg)
            q = self._heuristic_quality(resp.content, task)
            out.append(
                SampleResult(
                    content=resp.content,
                    quality_score=q,
                    cost=resp.cost,
                    strategy="naive",
                    metadata={"model": resp.model, "tokens_in": resp.tokens_in},
                )
            )
        return out

    async def importance_sample(
        self,
        task: str,
        n: int,
        model: str | None,
        constraints: list[str],
        config: SamplingConfig | None = None,
    ) -> list[SampleResult]:
        cfg = config or SamplingConfig()
        buffer = "\n".join(f"- {c}" for c in constraints)
        system = (
            "Constraint buffer — honor strictly:\n" + buffer
            if buffer
            else None
        )
        out: list[SampleResult] = []
        for _ in range(n):
            resp = await self._gen(task, model, cfg, system=system)
            q = self._heuristic_quality(resp.content, task)
            if buffer and all(c.lower() in resp.content.lower() for c in constraints if c):
                q = min(1.0, q + 0.1)
            out.append(
                SampleResult(
                    content=resp.content,
                    quality_score=q,
                    cost=resp.cost,
                    strategy="importance",
                    metadata={
                        "model": resp.model,
                        "constraints": constraints,
                    },
                )
            )
        return out

    def _discrete_pdf(
        self, content: str, strategy: StrategyName, pools: dict[StrategyName, list[str]]
    ) -> float:
        s = pools[strategy]
        n = len(s)
        if n == 0:
            return 0.0
        c = sum(1 for x in s if x == content)
        return c / n if c else 0.0

    def _mis_weight_for_sample(
        self,
        content: str,
        origin: StrategyName,
        n_free: int,
        n_rag: int,
        n_tool: int,
        pools: dict[StrategyName, list[str]],
    ) -> tuple[float, MISWeights]:
        n_map: dict[StrategyName, int] = {
            "free": n_free,
            "rag": n_rag,
            "tool": n_tool,
        }
        denom = 0.0
        terms: dict[str, float] = {}
        for k in ("free", "rag", "tool"):
            nk = n_map[k]
            if nk == 0:
                continue
            pk = self._discrete_pdf(content, k, pools)
            term = nk * pk
            terms[k] = term
            denom += term
        if denom <= 0:
            w = 1.0
        else:
            p_origin = self._discrete_pdf(content, origin, pools)
            num = n_map[origin] * p_origin
            w = num / denom if num > 0 else 0.0
        return w, MISWeights(weights={"balance": w}, balance_terms=terms)

    async def mis_sample(
        self,
        task: str,
        n_free: int,
        n_rag: int,
        n_tool: int,
        model: str | None,
        config: SamplingConfig | None = None,
    ) -> list[SampleResult]:
        cfg = config or SamplingConfig()
        pools: dict[StrategyName, list[str]] = {"free": [], "rag": [], "tool": []}
        raw: list[tuple[SampleResult, StrategyName]] = []

        async def draw_free() -> SampleResult:
            resp = await self._gen(task, model, cfg)
            q = self._heuristic_quality(resp.content, task)
            return SampleResult(
                content=resp.content,
                quality_score=q,
                cost=resp.cost,
                strategy="mis_free",
                metadata={"model": resp.model},
            )

        async def draw_rag() -> SampleResult:
            sys = "Use retrieval-style grounding; cite themes from the brief only."
            resp = await self._gen(task, model, cfg, system=sys)
            q = self._heuristic_quality(resp.content, task)
            return SampleResult(
                content=resp.content,
                quality_score=q,
                cost=resp.cost,
                strategy="mis_rag",
                metadata={"model": resp.model},
            )

        async def draw_tool() -> SampleResult:
            sys = "Simulate tool-augmented drafting: structure output with labeled sections."
            resp = await self._gen(task, model, cfg, system=sys)
            q = self._heuristic_quality(resp.content, task)
            return SampleResult(
                content=resp.content,
                quality_score=q,
                cost=resp.cost,
                strategy="mis_tool",
                metadata={"model": resp.model},
            )

        for _ in range(n_free):
            s = await draw_free()
            pools["free"].append(s.content)
            raw.append((s, "free"))
        for _ in range(n_rag):
            s = await draw_rag()
            pools["rag"].append(s.content)
            raw.append((s, "rag"))
        for _ in range(n_tool):
            s = await draw_tool()
            pools["tool"].append(s.content)
            raw.append((s, "tool"))

        combined: list[SampleResult] = []
        for sample, origin in raw:
            w, mw = self._mis_weight_for_sample(
                sample.content, origin, n_free, n_rag, n_tool, pools
            )
            md = dict(sample.metadata)
            md["mis_weight"] = w
            md["mis"] = mw.model_dump()
            combined.append(
                sample.model_copy(
                    update={
                        "metadata": md,
                        "strategy": f"mis_{origin}",
                    }
                )
            )
        return combined
