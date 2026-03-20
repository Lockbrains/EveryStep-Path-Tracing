from __future__ import annotations

import logging
import os

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import router, verify_adapters

load_dotenv(Path(__file__).resolve().parent / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="EveryStep Path Tracing — Art Bible API")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.on_event("startup")
async def startup() -> None:
    verify_adapters()
    logger.info(
        "Art Bible backend ready (OPENAI_API_KEY set: %s)",
        bool(os.environ.get("OPENAI_API_KEY")),
    )
