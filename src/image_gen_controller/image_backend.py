"""Gemini image call. Pattern matches google.genai usage: IMAGE+TEXT modalities.

Jev never sees pixels. This module only runs after code authorizes spend.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass
from typing import Any, Protocol

from image_gen_controller.config import Settings

logger = logging.getLogger(__name__)

# Estimated USD per image (1–2K tier). Same SKUs as common Gemini stills.
IMAGE_PRICES_USD = {
    "gemini-3-pro-image-preview": 0.134,
    "gemini-3.1-flash-image-preview": 0.067,
    "gemini-3.1-flash-lite-image": 0.034,
    "gemini-2.5-flash-image": 0.039,
}

PAINT_PREFIX = (
    "Commercial product still photograph. One product. Studio lighting. "
    "No logos, no readable text, no real people, no celebrity likeness.\n\n"
)


@dataclass(frozen=True)
class ImageResult:
    image_bytes: bytes
    mime_type: str
    model: str
    est_cost_usd: float


class ImageBackend(Protocol):
    def generate(self, prompt: str, model: str) -> ImageResult:
        """Return image bytes or raise. Caller decides whether to call."""


def estimate_image_cost_usd(model: str) -> float:
    return float(IMAGE_PRICES_USD.get((model or "").strip(), 0.0))


def build_paint_prompt(user_prompt: str) -> str:
    return PAINT_PREFIX + user_prompt


def extract_inline_image(response: Any) -> tuple[bytes, str]:
    """Pull the first image part out of a google.genai response."""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        raise RuntimeError("image model returned no candidates")
    parts = getattr(getattr(candidates[0], "content", None), "parts", None) or []
    for part in parts:
        inline = getattr(part, "inline_data", None)
        if inline is None:
            continue
        mime = getattr(inline, "mime_type", "") or ""
        if not mime.startswith("image/"):
            continue
        raw = inline.data
        image_bytes = base64.b64decode(raw) if isinstance(raw, str) else raw
        if not image_bytes:
            continue
        return bytes(image_bytes), mime
    raise RuntimeError("image model returned no image data")


class GeminiImageBackend:
    """One generate_content call. No cascade - Jev already chose the tier."""

    def __init__(self, settings: Settings, client=None):
        self._settings = settings
        self._client = client

    def generate(self, prompt: str, model: str) -> ImageResult:
        client = self._client or _make_client(self._settings.gemini_api_key)
        paint = build_paint_prompt(prompt)
        logger.info("Calling image model=%s prompt_chars=%s", model, len(paint))
        try:
            from google.genai import types as genai_types
        except ImportError as exc:
            raise RuntimeError("google-genai is not installed") from exc

        response = client.models.generate_content(
            model=model,
            contents=paint,
            config=genai_types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        image_bytes, mime_type = extract_inline_image(response)
        cost = estimate_image_cost_usd(model)
        logger.info(
            "Image model ok model=%s bytes=%s est_cost_usd=%.3f",
            model,
            len(image_bytes),
            cost,
        )
        return ImageResult(
            image_bytes=image_bytes,
            mime_type=mime_type,
            model=model,
            est_cost_usd=cost,
        )


def _make_client(api_key: str):
    from google import genai

    return genai.Client(api_key=api_key)
