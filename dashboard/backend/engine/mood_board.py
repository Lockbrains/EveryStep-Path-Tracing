"""Mood Board data models for multi-modal Art Bible generation."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GeneratedImage(BaseModel):
    id: str
    data: str  # base64
    mime_type: str = "image/png"


class MoodBoard(BaseModel):
    images: list[GeneratedImage] = Field(default_factory=list)
    annotation: str = ""
    step_index: int = 0
    strategy: str = ""

    @property
    def image_ids(self) -> list[str]:
        return [img.id for img in self.images]

    @property
    def is_empty(self) -> bool:
        return len(self.images) == 0 and not self.annotation
