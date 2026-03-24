"""Candidate diversity filter — prevents near-duplicate mood boards.

When MIS or multi-sample generates N candidates, some may be visually or
textually near-identical.  This module detects similarity and applies a
penalty so that the *best* candidate is also the most *distinct*.

Uses lightweight heuristics (no external ML models required):
- Annotation text: normalised Jaccard similarity on word n-grams.
- Images: byte-length ratio heuristic (cheap proxy when perceptual hashing
  is unavailable) — if two base64 images are within 5% length AND share a
  long common prefix, they are considered near-duplicates.
"""

from __future__ import annotations

import logging
from difflib import SequenceMatcher

from .mood_board import MoodBoard
from .scorer import MultiDimScore

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.80
DIVERSITY_PENALTY = 0.70
IMAGE_LENGTH_RATIO_THRESHOLD = 0.05


def _text_similarity(a: str, b: str) -> float:
    """Fast text similarity using SequenceMatcher (Ratcliff/Obershelp)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _image_similarity(board_a: MoodBoard, board_b: MoodBoard) -> float:
    """Cheap image similarity proxy based on data length and prefix overlap."""
    imgs_a = board_a.images
    imgs_b = board_b.images

    if not imgs_a or not imgs_b:
        return 0.0

    match_count = 0
    comparisons = 0

    for ia in imgs_a[:3]:
        for ib in imgs_b[:3]:
            comparisons += 1
            len_a, len_b = len(ia.data), len(ib.data)
            if len_a == 0 or len_b == 0:
                continue

            ratio = abs(len_a - len_b) / max(len_a, len_b)
            if ratio > IMAGE_LENGTH_RATIO_THRESHOLD:
                continue

            prefix_len = min(200, len_a, len_b)
            if ia.data[:prefix_len] == ib.data[:prefix_len]:
                match_count += 1

    return match_count / comparisons if comparisons > 0 else 0.0


def board_similarity(a: MoodBoard, b: MoodBoard) -> float:
    """Combined similarity score between two mood boards (0-1)."""
    text_sim = _text_similarity(a.annotation, b.annotation)
    img_sim = _image_similarity(a, b)
    return max(text_sim, img_sim)


def apply_diversity_penalty(
    candidates: list[MoodBoard],
    scores: list[MultiDimScore],
    threshold: float = SIMILARITY_THRESHOLD,
    penalty: float = DIVERSITY_PENALTY,
) -> list[MultiDimScore]:
    """Penalise candidates that are too similar to higher-ranked ones.

    Works in-place on the ``aggregate`` field and returns the same list.
    The first (highest-scoring) candidate is never penalised.
    """
    if len(candidates) <= 1:
        return scores

    ranked = sorted(range(len(scores)), key=lambda i: scores[i].aggregate, reverse=True)

    accepted_indices: list[int] = [ranked[0]]

    for idx in ranked[1:]:
        is_dup = False
        for acc_idx in accepted_indices:
            sim = board_similarity(candidates[idx], candidates[acc_idx])
            if sim >= threshold:
                is_dup = True
                logger.info(
                    "Diversity penalty: candidate %d similar to %d (%.2f >= %.2f)",
                    idx, acc_idx, sim, threshold,
                )
                break

        if is_dup:
            scores[idx].aggregate = round(scores[idx].aggregate * penalty, 4)
        accepted_indices.append(idx)

    return scores
