from __future__ import annotations

import asyncio
import base64
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncIterator

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from adapters.anthropic_adapter import AnthropicAdapter, HAIKU_INPUT_PER_1M, HAIKU_OUTPUT_PER_1M
from adapters.google_adapter import GEMINI_FLASH_INPUT_PER_1M, GEMINI_FLASH_OUTPUT_PER_1M, GoogleAdapter
from adapters.openai_adapter import GPT4O_MINI_INPUT_PER_1M, GPT4O_MINI_OUTPUT_PER_1M, OpenAIAdapter
from pipeline.art_bible import ArtBibleConfig, ArtBiblePipeline, PipelineEvent

router = APIRouter()

_pipeline_queues: dict[str, asyncio.Queue[PipelineEvent | None]] = {}
_experiment_queues: dict[str, asyncio.Queue[dict[str, Any] | None]] = {}

_KEY_NAMES = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "google": "GOOGLE_API_KEY",
}

# In-memory image store: id -> (base64_data, mime_type, filename)
_image_store: dict[str, tuple[str, str, str]] = {}

ALLOWED_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
MAX_IMAGE_SIZE = 20 * 1024 * 1024  # 20 MB


def _default_llm() -> GoogleAdapter:
    """Use Google adapter by default for multimodal image generation."""
    return GoogleAdapter()


def _scoring_llms() -> list:
    """Return all available LLM adapters for ensemble scoring.

    Generation still uses GoogleAdapter (only one with native image output),
    but scoring benefits from multi-LLM cross-validation.
    """
    from adapters.base import LLMAdapter

    llms: list[LLMAdapter] = [GoogleAdapter()]
    if os.environ.get("OPENAI_API_KEY"):
        llms.append(OpenAIAdapter())
    if os.environ.get("ANTHROPIC_API_KEY"):
        llms.append(AnthropicAdapter())
    return llms


def store_generated_image(b64: str, mime: str, filename: str) -> str:
    """Store a pipeline-generated image and return its ID."""
    img_id = str(uuid.uuid4())
    _image_store[img_id] = (b64, mime, filename)
    return img_id


# ---------------------------------------------------------------------------
# Image upload
# ---------------------------------------------------------------------------


class ImageUploadResponse(BaseModel):
    id: str
    filename: str
    mime_type: str
    size_bytes: int


@router.post("/images/upload", response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...)) -> ImageUploadResponse:
    ct = file.content_type or "application/octet-stream"
    if ct not in ALLOWED_MIME:
        raise HTTPException(400, f"Unsupported image type: {ct}. Allowed: {ALLOWED_MIME}")
    raw = await file.read()
    if len(raw) > MAX_IMAGE_SIZE:
        raise HTTPException(400, f"Image too large ({len(raw)} bytes). Max: {MAX_IMAGE_SIZE}")
    img_id = str(uuid.uuid4())
    b64 = base64.b64encode(raw).decode()
    _image_store[img_id] = (b64, ct, file.filename or "image")
    return ImageUploadResponse(
        id=img_id,
        filename=file.filename or "image",
        mime_type=ct,
        size_bytes=len(raw),
    )


@router.get("/images/{image_id}")
async def get_image(image_id: str) -> Response:
    entry = _image_store.get(image_id)
    if not entry:
        raise HTTPException(404, "Image not found")
    b64, mime, _ = entry
    return Response(content=base64.b64decode(b64), media_type=mime)


@router.get("/images", response_model=list[ImageUploadResponse])
async def list_images() -> list[ImageUploadResponse]:
    results = []
    for img_id, (b64, mime, fname) in _image_store.items():
        results.append(ImageUploadResponse(
            id=img_id,
            filename=fname,
            mime_type=mime,
            size_bytes=len(base64.b64decode(b64)),
        ))
    return results


@router.delete("/images/{image_id}")
async def delete_image(image_id: str) -> dict[str, str]:
    if image_id in _image_store:
        del _image_store[image_id]
    return {"status": "ok"}


def get_image_data(image_id: str) -> tuple[str, str] | None:
    """Get (base64, mime_type) for a stored image."""
    entry = _image_store.get(image_id)
    if not entry:
        return None
    return entry[0], entry[1]


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class PipelineRunResponse(BaseModel):
    run_id: str


@router.post("/pipeline/run", response_model=PipelineRunResponse)
async def start_pipeline(body: ArtBibleConfig) -> PipelineRunResponse:
    run_id = str(uuid.uuid4())
    q: asyncio.Queue[PipelineEvent | None] = asyncio.Queue()
    _pipeline_queues[run_id] = q

    image_data = []
    for img_id in (body.image_refs or []):
        entry = get_image_data(img_id)
        if entry:
            image_data.append(entry)

    async def worker() -> None:
        import logging
        logger = logging.getLogger(__name__)
        pipe = ArtBiblePipeline(
            _default_llm(),
            image_store_fn=store_generated_image,
            scoring_llms=_scoring_llms(),
        )
        try:
            async for ev in pipe.run(body.brief, body, image_data=image_data):
                await q.put(ev)
        except Exception as exc:
            logger.exception("Pipeline worker failed: %s", exc)
            from pipeline.art_bible import PipelineEvent
            from datetime import datetime, timezone
            await q.put(PipelineEvent(
                event_type="path_complete", step=-1,
                data={"error": str(exc)},
                timestamp=datetime.now(timezone.utc).isoformat(),
            ))
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


# ---------------------------------------------------------------------------
# Experiment (legacy)
# ---------------------------------------------------------------------------


class ExperimentConfig(BaseModel):
    name: str = "mc_ablation"
    brief: str = ""
    n_samples: int = 2
    strategy: str = "naive"
    model: str | None = None


class ExperimentRunResponse(BaseModel):
    run_id: str


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
        pipe = ArtBiblePipeline(
            _default_llm(),
            scoring_llms=_scoring_llms(),
        )
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


# ---------------------------------------------------------------------------
# Models & Keys
# ---------------------------------------------------------------------------


class ModelInfo(BaseModel):
    id: str
    provider: str
    input_per_1m_usd: float
    output_per_1m_usd: float


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


class KeyStatus(BaseModel):
    openai: bool
    anthropic: bool
    google: bool


class SetKeysRequest(BaseModel):
    openai: str | None = None
    anthropic: str | None = None
    google: str | None = None


@router.get("/keys/status", response_model=KeyStatus)
async def keys_status() -> KeyStatus:
    return KeyStatus(
        openai=bool(os.environ.get("OPENAI_API_KEY")),
        anthropic=bool(os.environ.get("ANTHROPIC_API_KEY")),
        google=bool(os.environ.get("GOOGLE_API_KEY")),
    )


@router.post("/keys", response_model=KeyStatus)
async def set_keys(body: SetKeysRequest) -> KeyStatus:
    for provider, env_var in _KEY_NAMES.items():
        value = getattr(body, provider)
        if value is not None:
            stripped = value.strip()
            if stripped:
                os.environ[env_var] = stripped
            else:
                os.environ.pop(env_var, None)
    return KeyStatus(
        openai=bool(os.environ.get("OPENAI_API_KEY")),
        anthropic=bool(os.environ.get("ANTHROPIC_API_KEY")),
        google=bool(os.environ.get("GOOGLE_API_KEY")),
    )


def verify_adapters() -> None:
    OpenAIAdapter()
    AnthropicAdapter()
    GoogleAdapter()
