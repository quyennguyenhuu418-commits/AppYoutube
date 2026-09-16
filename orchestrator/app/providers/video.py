"""
Video provider factory.

Selection rules:
  - Default: MultiVideoProvider (tự động fallback giữa các provider có sẵn)
  - Có thể override qua env: VIDEO_PROVIDER=veo (dùng 1 provider duy nhất)

Các provider hiện có:
  - kivest:    Kivest AI (FREE) - veo-3.1, grok-video, qwen-video
  - veo:       Google Veo 3.1 official (PAID, dùng GEMINI_API_KEY)
  - kling:     Kling 3.0 (FREE limited, 66 credits/tháng)

Nếu không có key nào → RuntimeError với hướng dẫn set up.
"""
from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import VideoProvider
from app.providers.kivest_video import KivestVideoProvider
from app.providers.kling_video import KlingVideoProvider
from app.providers.multi_video import MultiVideoProvider
from app.providers.veo_video import VeoVideoProvider

log = get_logger(__name__)


@lru_cache(maxsize=1)
def get_video_provider() -> VideoProvider:
    """Trả về video provider theo config.

    Selection:
      1. Nếu VIDEO_PROVIDER=multi (default) → MultiVideoProvider với fallback
      2. Nếu VIDEO_PROVIDER=<single>        → provider đó
    """
    choice = settings.video_provider.strip().lower() or "multi"

    if choice == "multi":
        log.info("Using MultiVideoProvider (automatic fallback)")
        return MultiVideoProvider()

    if choice == "kivest":
        log.info("Using KivestVideoProvider")
        return KivestVideoProvider()

    if choice == "veo":
        log.info("Using VeoVideoProvider")
        return VeoVideoProvider()

    if choice == "kling":
        log.info("Using KlingVideoProvider")
        return KlingVideoProvider()

    raise RuntimeError(
        f"Unknown VIDEO_PROVIDER='{choice}'. "
        f"Choose one of: multi (default), kivest, veo, kling"
    )
