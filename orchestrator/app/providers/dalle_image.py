"""
DALL-E image provider.

Generates a single image per request using OpenAI's `images.generate`.
If the OpenAI key is missing, the factory substitutes the
`PlaceholderImageProvider` which writes a colored PNG so the renderer
still has something to composite.
"""
from __future__ import annotations

from pathlib import Path

from openai import OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import ImageProvider, ImageRequest, ImageResponse

log = get_logger(__name__)


class DallEImageProvider(ImageProvider):
    name = "dalle"

    def __init__(self) -> None:
        if not settings.has_openai:
            raise RuntimeError("OPENAI_API_KEY is not set; DallEImageProvider cannot be used.")
        self._client = OpenAI(api_key=settings.openai_api_key)

    def generate(self, request: ImageRequest) -> ImageResponse:
        # DALL-E 3 supports specific sizes; map width/height to one of them.
        size = _nearest_dalle_size(request.width, request.height)
        try:
            result = self._client.images.generate(
                model=settings.openai_image_model,
                prompt=request.prompt,
                size=size,
                n=1,
            )
        except Exception as exc:
            log.error("DALL-E request failed: %s", exc)
            raise
        url = result.data[0].url
        if not url:
            raise RuntimeError("DALL-E returned no URL")

        # Download and save.
        import httpx
        out = Path(request.output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=60.0) as client:
            r = client.get(url)
            r.raise_for_status()
            out.write_bytes(r.content)
        log.info("Saved DALL-E image to %s (%d bytes)", out, out.stat().st_size)
        return ImageResponse(image_path=str(out))


def _nearest_dalle_size(w: int, h: int) -> str:
    candidates = {
        "1024x1024": (1024, 1024),
        "1792x1024": (1792, 1024),
        "1024x1792": (1024, 1792),
    }
    best = min(candidates.items(), key=lambda kv: abs(kv[1][0] - w) + abs(kv[1][1] - h))
    return best[0]
