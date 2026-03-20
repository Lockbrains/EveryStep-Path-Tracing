from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from adapters.anthropic_adapter import AnthropicAdapter, HAIKU_INPUT_PER_1M, HAIKU_OUTPUT_PER_1M
from adapters.google_adapter import GEMINI_FLASH_INPUT_PER_1M, GEMINI_FLASH_OUTPUT_PER_1M, GoogleAdapter
from adapters.openai_adapter import GPT4O_MINI_INPUT_PER_1M, GPT4O_MINI_OUTPUT_PER_1M, OpenAIAdapter
from pipeline.art_bible import ArtBibleConfig, ArtBiblePipeline, PipelineEvent

router = APIRouter()

_pipeline_queues: dict[str, asyncio.Queue[PipelineEvent | None]] = {}
_experiment_queues: dict[str, asyncio.Queue[dict[str, Any] | None]] = {}


def _default_llm() -> OpenAIAdapter:
    return OpenAIAdapter()


class ExperimentConfig(BaseModel):
    name: str = "mc_ablation"
    brief: str = ""
    n_samples: int = 2
    strategy: str = "naive"
    model: str | None = None


class PipelineRunResponse(BaseModel):
    run_id: str


class ExperimentRunResponse(BaseModel):
    run_id: str


class ModelInfo(BaseModel):
    id: str
    provider: str
    input_per_1m_usd: float
    output_per_1m_usd: float


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "ts": datetime.now(timezone.utc).isoformat()}


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def start_pipeline(body: ArtBibleConfig) -> PipelineRunResponse:
    run_id = str(uuid.uuid4())
    q: asyncio.Queue[PipelineEvent | None] = asyncio.Queue()
    _pipeline_queues[run_id] = q

    async def worker() -> None:
        pipe = ArtBiblePipeline(_default_llm())
        try:
            async for ev in pipe.run(body.brief, body):
                await q.put(ev)
        finally:
            await q.put(None)

    asyncio.create_task(worker())
    return PipelineRunResponse(run_id=run_id)


@router.get("/pipeline/stream/{run_id}")
async def stream_pipeline(run_id: str) -> EventSourceResponse:
    q = _pipeline_queues.get(run_id)
    if not q:
        raise HTTPException(status_code=404, detail="unknown run_id")

    async def gen() -> AsyncIterator[dict[str, Any]]:
        while True:
            ev = await q.get()
            if ev is None:
                yield {"data": json.dumps({"event_type": "done", "step": -1, "data": {}, "timestamp": ""})}
                break
            yield {"data": ev.model_dump_json()}

    return EventSourceResponse(gen())


@router.post("/experiment/run", response_model=ExperimentRunResponse)
async def start_experiment(body: ExperimentConfig) -> ExperimentRunResponse:
    run_id = str(uuid.uuid4())
    q: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    _experiment_queues[run_id] = q

    async def worker() -> None:
        cfg = ArtBibleConfig(
            brief=body.brief or "Untitled experiment brief",
            n_samples=body.n_samples,
            strategies=[body.strategy],
            model=body.model,
        )
        pipe = ArtBiblePipeline(_default_llm())
        try:
            async for ev in pipe.run(cfg.brief, cfg):
                await q.put({"kind": "experiment", "payload": ev.model_dump()})
        finally:
            await q.put(None)

    asyncio.create_task(worker())
    return ExperimentRunResponse(run_id=run_id)


@router.get("/experiment/stream/{run_id}")
async def stream_experiment(run_id: str) -> EventSourceResponse:
    q = _experiment_queues.get(run_id)
    if not q:
        raise HTTPException(status_code=404, detail="unknown run_id")

    async def gen() -> AsyncIterator[dict[str, Any]]:
        while True:
            item = await q.get()
            if item is None:
                yield {"data": json.dumps({"kind": "done"})}
                break
            yield {"data": json.dumps(item)}

    return EventSourceResponse(gen())


@router.get("/models", response_model=list[ModelInfo])
async def list_models() -> list[ModelInfo]:
    return [
        ModelInfo(
            id="gpt-4o-mini",
            provider="openai",
            input_per_1m_usd=GPT4O_MINI_INPUT_PER_1M,
            output_per_1m_usd=GPT4O_MINI_OUTPUT_PER_1M,
        ),
        ModelInfo(
            id="claude-3-5-haiku-20241022",
            provider="anthropic",
            input_per_1m_usd=HAIKU_INPUT_PER_1M,
            output_per_1m_usd=HAIKU_OUTPUT_PER_1M,
        ),
        ModelInfo(
            id="gemini-2.0-flash",
            provider="google",
            input_per_1m_usd=GEMINI_FLASH_INPUT_PER_1M,
            output_per_1m_usd=GEMINI_FLASH_OUTPUT_PER_1M,
        ),
    ]


def verify_adapters() -> None:
    OpenAIAdapter()
    AnthropicAdapter()
    GoogleAdapter()
