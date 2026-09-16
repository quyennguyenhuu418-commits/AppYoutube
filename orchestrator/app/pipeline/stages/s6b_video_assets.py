"""Stage 6b: video_assets — generates optional B-roll video clips per environment.

PROMPT X INTEGRATION:
    Sinh video B-roll (3-8s clip mỗi environment) bằng AI video generation.
    Mặc định OFF (settings.video_assets_enabled=False) để tương thích ngược.
    Khi bật, dùng MultiVideoProvider (Kie.ai/Kivest/Veo/Kling) để generate.

Behavior:
    - Backgrounds (image) vẫn được sinh bởi s6_assets.py như cũ.
    - Nếu video provider có sẵn VÀ video_assets_enabled=True:
        - Generate clip 5-8s cho MỖI environment
        - Lưu vào backgrounds/{env_id}.mp4
        - Cập nhật assets.json với key 'videos'
    - Renderer sẽ ưu tiên .mp4 nếu có, fallback về .png.

Backward compatibility:
    - Nếu không có video provider, stage là no-op.
    - Existing .png backgrounds vẫn hoạt động bình thường.

Provider priority (Sep 2026 verified):
    1. Kie.ai     - Kling 3.0 std $0.35, Veo 3 fast $0.30 (FREE 80 credits)
    2. Kivest     - 4 video/ngày free
    3. Veo 3.1    - $0.30-$1.28 (PAID qua Gemini key)
    4. Kling      - 66 credits/tháng free (cấm thương mại free tier)

Cost control (Sep 2026):
    - Với 80 credits Kie.ai ~80 clips 5s (~1-2 video/beat * 5 beats/job * 8 jobs)
    - Smart caching theo env_id nên 2 job CÙNG env sẽ reuse video (0 credits)
"""
from __future__ import annotations

import hashlib
import time
from pathlib import Path

from app.core.config import settings
from app.core.logging import get_logger
from app.core.paths import backgrounds_dir, read_json, stage_path, write_json
from app.pipeline.cache import should_skip
from app.pipeline.stages.base import Stage, StageContext
from app.providers.base import VideoRequest
from app.providers.video import get_video_provider

log = get_logger(__name__)


# ----------------------------------------------------------------------
# Prompt Engineering cho Kling 3.0 (qua Kie.ai)
# ----------------------------------------------------------------------
# Kling 3.0 thường hiểu tốt cấu trúc 5-trường sau (theo docs Kie.ai):
#   1. SUBJECT  - chủ thể chính (người/đồ vật/cảnh)
#   2. ACTION   - chuyển động / hành động đang diễn ra
#   3. SCENE    - bối cảnh & thời gian cụ thể
#   4. CAMERA   - góc quay, chuyển động camera
#   5. LIGHTING - ánh sáng + atmosphere
#
# Best practice: giữ prompt 50-150 từ, tránh abstraction, không chồng chỉnh sửa.
DOCUMENTARY_PROMPT_SUFFIX = (
    "Slow cinematic 24fps footage. Subtle camera push-in with slow parallax. "
    "Atmospheric particles drifting in the air. Soft volumetric light. "
    "Documentary B-roll, professional grade, shallow depth of field."
)


def _build_video_prompt(env_hint: str) -> str:
    """Build prompt tối ưu cho Kling 3.0 từ image hint gốc.

    Hint gốc từ _ENV_HINTS đã có sẵn mô tả scene (subject + scene + lighting).
    Hàm này chỉ thêm motion cues + camera cues phù hợp cho video.
    """
    return f"{env_hint.strip()} {DOCUMENTARY_PROMPT_SUFFIX}"


def _cache_key_for_env(eid: str, hint: str) -> str:
    """Cache key dựa trên (env_id, prompt_hash) — cho phép reuse khi cùng env."""
    prompt_hash = hashlib.sha1(hint.encode("utf-8")).hexdigest()[:12]
    return f"{eid}_{prompt_hash}"


class VideoAssetsStage(Stage):
    """Optional stage: generate AI video B-roll per environment.

    Skipped entirely if:
      - settings.video_assets_enabled = False (default)
      - No video provider available
      - No storyboard data
    """

    name = "video_assets"
    label = "B-roll Video AI"

    def run(self, ctx: StageContext) -> dict:
        # Check 1: Setting bật/tắt
        if not settings.video_assets_enabled:
            log.info("[%s] disabled (video_assets_enabled=False)", self.name)
            return {"enabled": False, "videos": {}}

        # Check 2: Provider có sẵn
        if not settings.has_any_video_provider:
            log.info("[%s] skipped — no video provider API key configured", self.name)
            return {"enabled": False, "reason": "no_provider", "videos": {}}

        # Load storyboard
        storyboard = ctx.state.get("storyboard") or read_json(stage_path(ctx.job_id, "storyboard"))
        bdir = backgrounds_dir(ctx.job_id)

        # Collect unique env ids
        env_ids: list[str] = []
        for beat in storyboard.get("beats", []):
            eid = beat.get("environment_id")
            if eid and eid not in env_ids:
                env_ids.append(eid)

        # Reuse prompt hints từ s6_assets (nếu có)
        from app.pipeline.stages.s6_assets import _ENV_HINTS
        duration = settings.video_assets_duration_sec
        aspect = settings.video_assets_aspect_ratio
        quality = settings.video_assets_quality

        provider = get_video_provider()
        available = getattr(provider, "available_providers", lambda: [provider.name])()
        log.info(
            "[%s] using provider=%s (%s), envs=%d, duration=%ds, aspect=%s, quality=%s",
            self.name, provider.name, available,
            len(env_ids), duration, aspect, quality,
        )

        saved: dict[str, str] = {}
        failed: dict[str, str] = {}
        cost_total = 0.0
        reused_cache = 0
        start_time = time.time()

        for eid in env_ids:
            target = bdir / f"{eid}.mp4"
            hint = _ENV_HINTS.get(eid)
            if hint is None:
                log.warning("[%s] no hint for env %s, skipping", self.name, eid)
                continue

            # Stage cache: nếu file .mp4 đã tồn tại + không stale → reuse
            if should_skip(target):
                log.info("[%s] cached %s", self.name, target)
                saved[eid] = str(target)
                reused_cache += 1
                continue

            video_prompt = _build_video_prompt(hint)
            log.info("[%s] generating video for %s", self.name, eid)
            try:
                req = VideoRequest(
                    prompt=video_prompt,
                    output_path=str(target),
                    duration_sec=duration,
                    aspect_ratio=aspect,
                    quality=quality,
                )
                t0 = time.time()
                resp = provider.generate(req)
                elapsed = time.time() - t0
                cost_total += resp.cost_estimate_usd
                log.info(
                    "[%s] ✓ %s: %.1fs, model=%s, ~$%.2f, file=%dMB",
                    self.name, eid, elapsed, resp.model, resp.cost_estimate_usd,
                    Path(resp.video_path).stat().st_size // (1024*1024),
                )
                saved[eid] = resp.video_path
            except Exception as exc:
                # Lỗi 1 env không chặn các env khác
                log.warning("[%s] failed for %s: %s", self.name, eid, exc)
                failed[eid] = str(exc)

        elapsed_total = time.time() - start_time

        # Persist mapping
        rel: dict[str, str] = {
            eid: str(Path(p).relative_to(settings.workspace_path))
            for eid, p in saved.items()
        }
        result = {
            "enabled": True,
            "provider": provider.name,
            "duration_sec": duration,
            "aspect_ratio": aspect,
            "quality": quality,
            "total_elapsed_sec": round(elapsed_total, 1),
            "total_cost_usd_estimate": round(cost_total, 2),
            "videos_cached": reused_cache,
            "videos_generated": len(saved) - reused_cache,
            "videos": saved,
            "failed": failed,
        }
        write_json(stage_path(ctx.job_id, "video_assets"), result)
        log.info(
            "[%s] done in %.1fs: %d videos (%d cached, %d new), %d failed, ~$%.2f estimated cost",
            self.name, elapsed_total, len(saved),
            reused_cache, len(saved) - reused_cache, len(failed), cost_total,
        )
        return result
