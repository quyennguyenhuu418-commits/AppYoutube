"""
Asset Provider abstraction.

Decouples asset engine from specific providers (DALL-E, Flux, etc.).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from app.core.logging import get_logger

log = get_logger(__name__)


class ProviderType(str, Enum):
    IMAGE = "image"
    SVG = "svg"
    VECTOR = "vector"
    PROCEDURAL = "procedural"


@dataclass
class AssetProviderRequest:
    """A request to generate an asset via a provider."""
    prompt: str
    style_profile: dict[str, Any] = field(default_factory=dict)
    width: int = 1920
    height: int = 1080
    seed: int | None = None
    output_format: str = "png"
    provider_type: ProviderType = ProviderType.IMAGE
    version: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    output_path: str | Path = ""


@dataclass
class AssetProviderResponse:
    """A response from an asset provider."""
    image_path: str = ""
    content: str = ""  # for SVG or vector
    metadata: dict[str, Any] = field(default_factory=dict)
    duration_sec: float = 0.0
    provider: str = ""
    model: str = ""
    error: str = ""


def asset_provider_generate(req: AssetProviderRequest) -> AssetProviderResponse:
    """Generate an asset via the active provider.

    For PNG/rendered images: uses ImageProvider (DALL-E or Placeholder).
    For SVG: uses procedural SVG generation (deterministic).
    For now, all assets go through the existing image provider.

    This is the boundary that lets the asset engine stay
    provider-agnostic while delegating to existing infrastructure.
    """
    start = datetime.utcnow()

    from app.providers.image import get_image_provider
    from app.providers.base import ImageRequest

    # For now, route everything through the image provider
    # (extensible: SVG could go through svg_generator, vector through path-builder)
    provider = get_image_provider()
    output_path = str(req.output_path) if req.output_path else ""
    if not output_path:
        # Use cache dir for temporary
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.close()
        output_path = tmp.name

    img_req = ImageRequest(
        prompt=req.prompt,
        output_path=output_path,
        width=req.width,
        height=req.height,
    )

    try:
        resp = provider.generate(img_req)
        duration = (datetime.utcnow() - start).total_seconds()
        return AssetProviderResponse(
            image_path=resp.image_path,
            duration_sec=duration,
            provider=provider.__class__.__name__,
            model=getattr(provider, "model", ""),
        )
    except Exception as exc:
        log.error("[provider] generation failed: %s", exc)
        return AssetProviderResponse(
            error=str(exc),
            duration_sec=(datetime.utcnow() - start).total_seconds(),
        )
