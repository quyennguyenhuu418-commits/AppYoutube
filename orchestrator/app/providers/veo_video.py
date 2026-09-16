"""
Veo 3.1 Official Provider - Google AI Studio / Gemini API.

API chính thức của Google cho model Veo 3.1.
Docs:
  - https://ai.google.dev/gemini-api/docs/video
  - https://ai.google.dev/gemini-api/docs/changelog (Veo 3.1 GA: veo-3.1-generate-001)

QUAN TRỌNG (Sep 2026 update):
  - veo-2.0-generate-001 ĐÃ BỊ DEPRECATED (tắt ngày 30/06/2026)
  - veo-3.0-generate-001 ĐÃ BỊ DEPRECATED
  - Chỉ dùng veo-3.1-generate-001 (GA) hoặc veo-3.1-fast-generate-preview (Lite)
  - Tier 1 quota: 10 video/ngày (rất hạn chế)
  - Cần enable billing để tăng quota

PRICING (ước tính):
  - Veo 3.1 Quality 1080p: ~$1.28/video
  - Veo 3.1 Fast:         ~$0.30-0.40/video
  - Veo 3.1 Lite Preview: rẻ nhất, tốt cho iteration

Usage:
    >>> provider = VeoVideoProvider()
    >>> req = VideoRequest(prompt="A cinematic shot of ...",
    ...                    output_path="/tmp/scene.mp4",
    ...                    quality="draft")  # dùng veo-fast
    >>> resp = provider.generate(req)
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import VideoProvider, VideoRequest, VideoResponse

log = get_logger(__name__)


class VeoVideoProvider(VideoProvider):
    """Google Veo 3.1 official provider (Gemini API)."""

    name = "veo"

    # Model IDs (Sep 2026 - đã verify còn active)
    MODELS = {
        "draft":   "veo-3.1-fast-generate-preview",   # Rẻ nhất, nhanh nhất
        "standard":"veo-3.1-generate-preview",        # Preview (có thể miễn phí với quota)
        "high":    "veo-3.1-generate-001",            # GA, chất lượng cao nhất
    }

    # Pricing ước tính (USD) cho cost monitoring
    COST_ESTIMATE = {
        "veo-3.1-fast-generate-preview": 0.30,
        "veo-3.1-generate-preview":      0.60,
        "veo-3.1-generate-001":          1.28,
    }

    # Polling
    POLL_INTERVAL_SEC = 10.0
    DEFAULT_TIMEOUT_SEC = 600.0    # Veo 3.1 có thể mất 3-6 phút

    def __init__(self) -> None:
        api_key = settings.gemini_api_key  # Dùng chung Gemini API key
        if not api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set; VeoVideoProvider cannot be used. "
                "Lấy key miễn phí tại https://aistudio.google.com/apikey"
            )
        self._api_key = api_key
        self._base_url = "https://generativelanguage.googleapis.com/v1beta"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(self, request: VideoRequest) -> VideoResponse:
        """Submit video generation → poll operations → download MP4."""
        model = self._pick_model(request.quality)
        log.info("[Veo] generating %ds %s video: %s",
                 request.duration_sec, model, request.prompt[:80])

        operation = self._start_long_running_op(model, request)

        # Poll cho tới khi done
        video_url = self._wait_for_completion(operation, model=model)
        if not video_url:
            raise RuntimeError(f"Veo operation did not return a video URL: {operation}")

        self._download_video(video_url, request.output_path)

        return VideoResponse(
            video_path=request.output_path,
            duration_sec=float(request.duration_sec),
            provider=self.name,
            model=model,
            cost_estimate_usd=self.COST_ESTIMATE.get(model, 0.0),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pick_model(self, quality: str) -> str:
        if settings.veo_model:
            return settings.veo_model
        return self.MODELS.get(quality, self.MODELS["standard"])

    def _start_long_running_op(self, model: str, req: VideoRequest) -> dict:
        """POST :predictLongRunning để bắt đầu generation."""
        url = f"{self._base_url}/models/{model}:predictLongRunning"
        params = {"key": self._api_key}

        # Instance theo Google schema
        instance: dict = {"prompt": req.prompt}
        if req.reference_image_path:
            # Image-to-video: base64 encode ảnh
            instance["image"] = {
                "bytesBase64Encoded": self._encode_image_b64(req.reference_image_path),
                "mimeType": "image/png",
            }

        payload = {
            "instances": [instance],
            "parameters": {
                "aspectRatio": req.aspect_ratio.replace(":", "x"),  # "16:9" -> "16x9"
                "durationSeconds": req.duration_sec,
                "personGeneration": "dont_allow",  # Mặc định an toàn cho documentary
            },
        }
        if req.seed is not None:
            payload["parameters"]["seed"] = req.seed

        headers = {"Content-Type": "application/json"}
        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, params=params, headers=headers, json=payload)
            r.raise_for_status()
            op = r.json()
        log.debug("[Veo] started operation: %s", op.get("name"))
        return op

    def _wait_for_completion(self, operation: dict, model: str) -> str | None:
        """Poll operation cho tới khi done=true. Trả về video URL."""
        op_name = operation.get("name")
        if not op_name:
            raise RuntimeError(f"Veo operation missing 'name': {operation}")

        url = f"{self._base_url}/{op_name}"
        params = {"key": self._api_key}
        deadline = time.time() + self.DEFAULT_TIMEOUT_SEC
        while time.time() < deadline:
            with httpx.Client(timeout=30.0) as client:
                r = client.get(url, params=params)
                r.raise_for_status()
                op = r.json()
            done = op.get("done", False)
            if done:
                # Kiểm tra error
                if "error" in op:
                    err = op["error"]
                    raise RuntimeError(f"Veo operation failed: {err}")
                # Trả về URL từ response
                videos = (op.get("response") or {}).get("videos") or []
                if videos:
                    return videos[0].get("gcsUri") or videos[0].get("url")
                raise RuntimeError(f"Veo operation done but no video: {op}")
            log.info("[Veo] operation %s still running — sleeping %.0fs",
                     op_name.split("/")[-1], self.POLL_INTERVAL_SEC)
            time.sleep(self.POLL_INTERVAL_SEC)
        raise TimeoutError(f"Veo operation {op_name} did not finish within {self.DEFAULT_TIMEOUT_SEC}s")

    def _download_video(self, url: str, dest: str) -> None:
        """Tải MP4 từ GCS URI hoặc HTTPS URL."""
        out = Path(dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        # GCS URI cần ?key=... nếu signed, nhưng thường response trả URL có sẵn
        with httpx.Client(timeout=self.DEFAULT_TIMEOUT_SEC, follow_redirects=True) as client:
            with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(out, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
        log.info("[Veo] saved %s (%d bytes)", out, out.stat().st_size)

    def _encode_image_b64(self, path: str) -> str:
        import base64
        return base64.b64encode(Path(path).read_bytes()).decode("ascii")


class VeoRateLimitError(RuntimeError):
    """Raised khi Veo trả 429/RESOURCE_EXHAUSTED. MultiVideoProvider sẽ fallback."""
    pass
