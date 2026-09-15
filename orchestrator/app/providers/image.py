"""
Image provider factory.

Selection rules:
  - If `OPENAI_API_KEY` is set -> DALL-E provider.
  - Otherwise -> Placeholder provider (solid-color PNG, deterministic by prompt).
"""
from __future__ import annotations

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import ImageProvider
from app.providers.dalle_image import DallEImageProvider
from app.providers.placeholder_image import PlaceholderImageProvider

log = get_logger(__name__)


def get_image_provider() -> ImageProvider:
    if settings.has_openai:
        log.info("Using DALL-E image provider.")
        return DallEImageProvider()
    log.warning("OPENAI_API_KEY not set; using PlaceholderImageProvider (solid color PNGs).")
    return PlaceholderImageProvider()
