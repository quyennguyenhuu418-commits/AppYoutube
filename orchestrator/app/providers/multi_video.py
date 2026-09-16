"""
MultiVideoProvider - Wrapper với fallback logic.

Tự động chuyển đổi giữa các video provider khi provider chính fail hoặc bị rate-limit.

Ưu tiên mặc định (Sep 2026):
  1. Kie.ai        (FREE 80 credits)  - 30+ models qua 1 key (Veo 3.1, Kling, Sora 2...)
  2. Kivest AI     (FREE 4/day)        - Veo 3.1, Grok Video, Qwen Video
  3. Veo 3.1       (PAID)              - Google AI Studio
  4. Kling 3.0     (FREE 66/tháng)     - Quality tốt nhưng cấm thương mại free tier

Có thể tùy chỉnh qua VIDEO_PROVIDER_PRIORITY env var:
  VIDEO_PROVIDER_PRIORITY=kivest,kie,veo,kling

Lợi ích:
  - Luôn có fallback nếu 1 provider bị rate-limit / downtime
  - Có thể mix free + paid để tối ưu cost
  - Dễ thêm provider mới chỉ bằng cách register vào danh sách

Usage:
    >>> provider = MultiVideoProvider()
    >>> req = VideoRequest(prompt="...", output_path="/tmp/x.mp4")
    >>> resp = provider.generate(req)   # Tự động thử từng provider
"""
from __future__ import annotations

import time
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import VideoProvider, VideoRequest, VideoResponse
from app.providers.kivest_video import KivestRateLimitError, KivestVideoProvider
from app.providers.kling_video import KlingRateLimitError, KlingVideoProvider
from app.providers.veo_video import VeoRateLimitError, VeoVideoProvider

log = get_logger(__name__)


class MultiVideoProvider(VideoProvider):
    """Provider wrapper tự động fallback giữa nhiều AI video services."""

    name = "multi"

    # Provider registry: name -> (class, required_settings_attr)
    REGISTRY: dict[str, type[VideoProvider]] = {
        "kivest": KivestVideoProvider,
        "veo": VeoVideoProvider,
        "kling": KlingVideoProvider,
    }

    # Default priority order
    DEFAULT_PRIORITY = ["kivest", "veo", "kling"]

    def __init__(self) -> None:
        # Parse priority từ env (nếu có), không thì dùng default
        priority_str = settings.video_provider_priority.strip()
        if priority_str:
            self._priority = [p.strip().lower() for p in priority_str.split(",") if p.strip()]
        else:
            self._priority = list(self.DEFAULT_PRIORITY)

        # Validate
        for p in self._priority:
            if p not in self.REGISTRY:
                raise RuntimeError(
                    f"Unknown video provider '{p}' in VIDEO_PROVIDER_PRIORITY. "
                    f"Available: {list(self.REGISTRY.keys())}"
                )

        # Instantiate các provider (skip nếu thiếu key)
        self._providers: list[VideoProvider] = []
        for name in self._priority:
            cls = self.REGISTRY[name]
            try:
                provider = cls()
                if not provider.is_available():
                    log.warning("[MultiVideo] %s: not available, skipping", name)
                    continue
                self._providers.append(provider)
                log.info("[MultiVideo] registered provider: %s", name)
            except RuntimeError as exc:
                log.warning("[MultiVideo] %s: %s — skipping", name, exc)

        if not self._providers:
            raise RuntimeError(
                "MultiVideoProvider: no video providers available. "
                "Set at least one of: KIVEST_API_KEY, GEMINI_API_KEY, KLING_API_KEY"
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        return bool(self._providers)

    def available_providers(self) -> list[str]:
        """Danh sách provider đã register thành công."""
        return [p.name for p in self._providers]

    def generate(self, request: VideoRequest) -> VideoResponse:
        """Thử tuần tự các provider cho tới khi 1 cái thành công."""
        out_path = Path(request.output_path)
        last_exc: Exception | None = None
        total_elapsed = time.time()
        cost_total = 0.0

        for i, provider in enumerate(self._providers, start=1):
            provider_label = f"[{i}/{len(self._providers)} {provider.name}]"
            log.info(
                "%s trying %s for prompt: %s",
                provider_label, provider.name, request.prompt[:60],
            )
            t0 = time.time()
            try:
                resp = provider.generate(request)
                cost_total += resp.cost_estimate_usd
                log.info(
                    "%s SUCCESS in %.1fs (model=%s, cost=$%.2f)",
                    provider_label, time.time() - t0, resp.model, resp.cost_estimate_usd,
                )
                log.info(
                    "[MultiVideo] total: %.1fs, $%.2f, used=%s",
                    time.time() - total_elapsed, cost_total, provider.name,
                )
                return resp
            except (KivestRateLimitError, VeoRateLimitError, KlingRateLimitError) as exc:
                # Rate-limit cụ thể → fallback nhanh
                log.warning(
                    "%s rate-limited (%.1fs): %s — falling back to next provider",
                    provider_label, time.time() - t0, exc,
                )
                last_exc = exc
                continue
            except Exception as exc:
                # Lỗi khác (network, auth, schema) → log và fallback
                log.warning(
                    "%s failed (%.1fs): %s — falling back",
                    provider_label, time.time() - t0, exc,
                )
                last_exc = exc
                continue

        # Hết provider
        raise RuntimeError(
            f"All {len(self._providers)} video providers failed. "
            f"Available: {[p.name for p in self._providers]}. "
            f"Last error: {last_exc}"
        )
