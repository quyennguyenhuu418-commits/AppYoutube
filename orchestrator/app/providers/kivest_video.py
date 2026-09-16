"""
Kivest AI Provider - FREE API cho video generation.

Kivest cung cấp OpenAI-compatible API cho các model video AI hàng đầu:
  - veo-3.1   (Google Veo 3.1) - chất lượng cao nhất
  - grok-video (xAI Grok) - chất lượng cao, nhanh
  - qwen-video (Alibaba Qwen) - tốt cho B-roll cinematic

FREE TIER (theo research tháng 9/2026):
  - Video generation: 1 RPM, 4 RPD (reset midnight UTC)
  - Không cần credit card
  - Đăng nhập Google để lấy API key
  - Endpoint: https://YOUR_WORKER_URL/v1/video/generations
  - Docs: https://ai.ezif.in/docs

Usage:
    >>> provider = KivestVideoProvider()
    >>> req = VideoRequest(prompt="A cat walking across a sunny garden",
    ...                    output_path="/tmp/cat.mp4")
    >>> resp = provider.generate(req)
    >>> print(resp.video_path)
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


class KivestVideoProvider(VideoProvider):
    """Kivest AI video provider — hỗ trợ veo-3.1, grok-video, qwen-video."""

    name = "kivest"

    # Free tier limits
    FREE_RPM = 1                         # 1 request per minute
    FREE_RPD = 4                         # 4 requests per day
    DEFAULT_TIMEOUT_SEC = 300            # Video gen có thể mất 1-5 phút

    # Map model_hint -> Kivest model ID
    MODEL_MAP = {
        "veo": "veo-3.1",
        "veo-fast": "veo-3.1-fast-generate-preview",  # Lite/Fast variant nếu có
        "grok": "grok-video",
        "qwen": "qwen-video",
        "default": "veo-3.1",
    }

    def __init__(self) -> None:
        api_key = settings.kivest_api_key
        if not api_key:
            raise RuntimeError(
                "KIVEST_API_KEY is not set; KivestVideoProvider cannot be used. "
                "Sign up free at https://ai.ezif.in/docs"
            )
        self._api_key = api_key
        self._base_url = settings.kivest_base_url.rstrip("/")
        # Track rate limit để tránh spam
        self._last_request_ts: float = 0.0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def is_available(self) -> bool:
        """Kivest được coi là available nếu có key. Rate-limit thực xử lý ở generate()."""
        return bool(self._api_key)

    def generate(self, request: VideoRequest) -> VideoResponse:
        """Submit video generation job, poll cho tới khi xong, tải MP4 về output_path."""
        model = self._pick_model(request.quality)
        log.info(
            "[Kivest] generating %ds %s video: %s",
            request.duration_sec, model, request.prompt[:80],
        )

        # 1) Enforce 1 RPM (free tier)
        self._respect_rate_limit()

        # 2) Submit task
        try:
            task_resp = self._submit_task(model, request)
        except httpx.HTTPStatusError as exc:
            # 429 → rate limited → throw RateLimitError để MultiVideoProvider fallback
            if exc.response.status_code == 429:
                raise KivestRateLimitError(str(exc)) from exc
            raise

        task_id = task_resp.get("id") or task_resp.get("task_id")
        if not task_id:
            raise RuntimeError(f"Kivest submit returned no task id: {task_resp}")

        # 3) Poll
        video_url = self._poll_for_url(task_id, model=model)
        if not video_url:
            raise RuntimeError(f"Kivest task {task_id} did not return a video URL")

        # 4) Download
        self._download_video(video_url, request.output_path)

        # 5) Cost estimate (Kivest miễn phí, $0 cho free tier)
        return VideoResponse(
            video_path=request.output_path,
            duration_sec=float(request.duration_sec),
            provider=self.name,
            model=model,
            cost_estimate_usd=0.0,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _pick_model(self, quality: str) -> str:
        """Map quality hint -> Kivest model. Có thể override qua KIVEST_MODEL env."""
        env_model = settings.kivest_model
        if env_model:
            return env_model
        if quality == "draft":
            return self.MODEL_MAP["grok"]   # Grok nhanh nhất
        if quality == "high":
            return self.MODEL_MAP["veo"]    # Veo chất lượng cao nhất
        return self.MODEL_MAP["default"]

    def _respect_rate_limit(self) -> None:
        """Đảm bảo không vượt quá 1 RPM. Sleep nếu cần."""
        if self._last_request_ts > 0:
            elapsed = time.time() - self._last_request_ts
            wait = 60.0 - elapsed
            if wait > 0:
                log.info("[Kivest] rate-limit guard: sleeping %.1fs", wait)
                time.sleep(wait)
        self._last_request_ts = time.time()

    def _submit_task(self, model: str, req: VideoRequest) -> dict:
        """POST /v1/video/generations — Kivest trả task_id ngay (sync mode)."""
        url = f"{self._base_url}/v1/video/generations"
        payload = {
            "model": model,
            "prompt": req.prompt,
        }
        # Các field optional (nếu Kivest hỗ trợ)
        if req.aspect_ratio:
            payload["aspect_ratio"] = req.aspect_ratio
        if req.duration_sec:
            payload["duration"] = req.duration_sec

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        # Kivest có thể trả SSE theo mặc định → set stream=false để nhận JSON
        if "stream" not in payload:
            payload["stream"] = False

        with httpx.Client(timeout=30.0) as client:
            r = client.post(url, headers=headers, json=payload)
            r.raise_for_status()
            # Kivest đôi khi trả SSE thay vì JSON → parse thủ công
            raw = r.text
            content_type = r.headers.get("content-type", "")
            if "text/event-stream" in content_type or raw.startswith("data:"):
                log.debug("[Kivest] got SSE response, parsing last data chunk")
                data = self._parse_sse_response(raw)
            else:
                data = r.json()
        log.debug("[Kivest] submit response: %s", json.dumps(data)[:200])
        return data

    def _parse_sse_response(self, raw: str) -> dict:
        """Parse Server-Sent Events: lấy chunk JSON cuối cùng (trước [DONE])."""
        import json as _json
        last_data = None
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:") and line != "data: [DONE]":
                payload = line[5:].strip()
                if payload:
                    try:
                        last_data = _json.loads(payload)
                    except _json.JSONDecodeError:
                        continue
        if last_data is None:
            raise RuntimeError(f"Kivest SSE response contained no valid JSON chunks: {raw[:200]}")
        return last_data

    def _poll_for_url(self, task_id: str, model: str, max_wait: int = 240) -> str | None:
        """Poll cho tới khi task xong. Nếu response sync đã có URL thì trả về luôn."""
        # Nhiều Kivest deployments trả video URL sync trong submit response.
        # Hàm này xử lý cả 2 case:
        #   1) submit đã trả URL → trả về luôn (poll 1 lần thấy status=done)
        #   2) submit trả status=processing → poll mỗi 5s
        url = f"{self._base_url}/v1/video/generations/{task_id}"
        headers = {"Authorization": f"Bearer {self._api_key}"}
        deadline = time.time() + max_wait
        interval = 5.0
        while time.time() < deadline:
            try:
                with httpx.Client(timeout=30.0) as client:
                    r = client.get(url, headers=headers)
                    r.raise_for_status()
                    data = r.json()
            except httpx.HTTPError as exc:
                log.warning("[Kivest] poll error (will retry): %s", exc)
                time.sleep(interval)
                continue

            status = (data.get("status") or "").lower()
            # Thử nhiều key khác nhau (Kivest đôi khi đổi schema)
            video_url = (
                data.get("video_url")
                or data.get("url")
                or (data.get("output") or {}).get("video_url")
                or (data.get("result") or {}).get("url")
            )
            if status in {"succeeded", "completed", "done"} and video_url:
                return video_url
            if status in {"failed", "error", "cancelled"}:
                err = data.get("error") or data.get("message") or "unknown"
                raise RuntimeError(f"Kivest task {task_id} failed: {err}")
            log.info("[Kivest] task %s status=%s — sleeping %.0fs", task_id, status, interval)
            time.sleep(interval)
        raise TimeoutError(f"Kivest task {task_id} did not complete within {max_wait}s")

    def _download_video(self, url: str, dest: str) -> None:
        """Tải MP4 từ URL tạm về output_path."""
        out = Path(dest)
        out.parent.mkdir(parents=True, exist_ok=True)
        with httpx.Client(timeout=self.DEFAULT_TIMEOUT_SEC, follow_redirects=True) as client:
            with client.stream("GET", url) as r:
                r.raise_for_status()
                with open(out, "wb") as f:
                    for chunk in r.iter_bytes(chunk_size=64 * 1024):
                        f.write(chunk)
        size = out.stat().st_size
        log.info("[Kivest] saved %s (%d bytes)", out, size)


class KivestRateLimitError(RuntimeError):
    """Raised khi Kivest trả 429. MultiVideoProvider sẽ fallback sang provider khác."""
    pass
