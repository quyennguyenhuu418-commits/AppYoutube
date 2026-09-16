"""
Kling AI Provider - Kuaishou (快手) video generation.

Kling 3.0 là model video AI từ Kuaishou — chất lượng rất cao, đặc biệt về
character animation và motion. Hỗ trợ cả text-to-video và image-to-video.

FREE TIER (Sep 2026):
  - 66 credits/tháng (~2-3 video 5s) — không reset daily
  - Free tier CẤM sử dụng thương mại (cần paid plan để monetize)
  - API: https://api.klingai.com (cần JWT token)

PRICING (tham khảo):
  - Kling 3.0 std 5s:  ~$0.35/video (no audio)
  - Kling 3.0 pro 5s:  ~$0.68/video (with audio)
  - Kling 2.6 HD 5s:   ~$0.28/video (with audio)

Docs: https://docs.klingai.com/

Usage:
    >>> provider = KlingVideoProvider()
    >>> req = VideoRequest(prompt="A panda dancing in the snow", output_path="/tmp/panda.mp4")
    >>> resp = provider.generate(req)
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.base import VideoProvider, VideoRequest, VideoResponse

log = get_logger(__name__)


class KlingVideoProvider(VideoProvider):
    name = "kling"

    BASE_URL = "https://api.klingai.com"

    # Models (Sep 2026)
    MODELS = {
        "draft":    "kling-v2",                      # Stable, rẻ
        "standard": "kling-v3-std",                  # Standard quality
        "high":     "kling-v3-pro",                  # Pro quality, with audio
    }

    COST_ESTIMATE = {
        "kling-v2":     0.20,
        "kling-v3-std": 0.35,
        "kling-v3-pro": 0.68,
    }

    POLL_INTERVAL_SEC = 8.0
    DEFAULT_TIMEOUT_SEC = 600.0

    def __init__(self) -> None:
        ak = settings.kling_access_key
        sk = settings.kling_secret_key
        if not ak or not sk:
            raise RuntimeError(
                "KLING_ACCESS_KEY/SECRET_KEY not set; KlingVideoProvider cannot be used. "
                "Đăng ký tại https://klingai.com"
            )
        self._ak = ak
        self._sk = sk

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        return bool(self._ak) and bool(self._sk)

    def generate(self, request: VideoRequest) -> VideoResponse:
        model = self._pick_model(request.quality)
        log.info("[Kling] generating %ds %s video: %s",
                 request.duration_sec, model, request.prompt[:80])

        task_id = self._submit_task(model, request)
        videos = self._poll_for_result(task_id)
        if not videos:
            raise RuntimeError(f"Kling task {task_id} did not return videos")
        # Lấy URL video đầu tiên
        video_url = videos[0].get("url")
        if not video_url:
            raise RuntimeError(f"Kling videos[0] missing url: {videos[0]}")

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
        if settings.kling_model:
            return settings.kling_model
        return self.MODELS.get(quality, self.MODELS["standard"])

    def _make_token(self) -> str:
        """Kling API dùng JWT-style token (HS256) đơn giản với ak/sk."""
        header = {"alg": "HS256", "typ": "JWT"}
        now = int(time.time())
        payload = {
            "iss": self._ak,
            "exp": now + 1800,           # 30 phút
            "nbf": now - 5,
        }

        def b64url(d: dict) -> str:
            return base64.urlsafe_b64encode(json.dumps(d, separators=(",", ":")).encode()).rstrip(b"=").decode()

        header_b64 = b64url(header)
        payload_b64 = b64url(payload)
        signing_input = f"{header_b64}.{payload_b64}".encode()
        sig = hmac.new(self._sk.encode(), signing_input, hashlib.sha256).digest()
        sig_b64 = base64.urlsafe_b64encode(sig).rstrip(b"=").decode()
        return f"{header_b64}.{payload_b64}.{sig_b64}"

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self._make_token()}",
            "Content-Type": "application/json",
        }

    def _submit_task(self, model: str, req: VideoRequest) -> str:
        """POST /v1/videos/text2video (hoặc image2video)."""
        url = f"{self.BASE_URL}/v1/videos/text2video"
        payload = {
            "model_name": model,
            "prompt": req.prompt,
            "duration": "5",   # Kling chỉ hỗ trợ 5 hoặc 10s
            "aspect_ratio": req.aspect_ratio,
            "mode": "std",
        }
        if req.reference_image_path:
            # Switch sang image2video
            url = f"{self.BASE_URL}/v1/videos/image2video"
            payload["image"] = self._encode_image_b64(req.reference_image_path)

        with httpx.Client(timeout=60.0) as client:
            r = client.post(url, headers=self._headers(), json=payload)
            r.raise_for_status()
            data = r.json()

        task_id = (data.get("data") or {}).get("task_id")
        if not task_id:
            raise RuntimeError(f"Kling submit returned no task_id: {data}")
        log.debug("[Kling] task_id=%s", task_id)
        return task_id

    def _poll_for_result(self, task_id: str) -> list[dict]:
        """GET /v1/videos/text2video/{task_id} cho tới khi done."""
        url = f"{self.BASE_URL}/v1/videos/text2video/{task_id}"
        deadline = time.time() + self.DEFAULT_TIMEOUT_SEC
        while time.time() < deadline:
            with httpx.Client(timeout=30.0) as client:
                r = client.get(url, headers=self._headers())
                r.raise_for_status()
                data = r.json()

            task = data.get("data") or {}
            status = (task.get("task_status") or "").lower()
            if status == "succeed":
                return task.get("task_result", {}).get("videos") or []
            if status == "failed":
                raise RuntimeError(f"Kling task {task_id} failed: {task.get('task_status_msg')}")
            log.info("[Kling] task %s status=%s — sleeping %.0fs",
                     task_id, status, self.POLL_INTERVAL_SEC)
            time.sleep(self.POLL_INTERVAL_SEC)
        raise TimeoutError(f"Kling task {task_id} did not finish within {self.DEFAULT_TIMEOUT_SEC}s")

    def _download_video(self, url: str, dest: str) -> None:
        out = Path(dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=self.DEFAULT_TIMEOUT_SEC, follow_redirects=True) as client:
            with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(out, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
        log.info("[Kling] saved %s (%d bytes)", out, out.stat().st_size)

    def _encode_image_b64(self, path: str) -> str:
        return base64.b64encode(Path(path).read_bytes()).decode()


class KlingRateLimitError(RuntimeError):
    pass
